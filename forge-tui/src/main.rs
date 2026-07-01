use crossterm::{
    event::{self, DisableMouseCapture, EnableMouseCapture, Event, KeyCode},
    execute,
    terminal::{disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen},
};
use forge_core::AgentEvent;
use ratatui::{
    backend::CrosstermBackend,
    layout::{Constraint, Direction, Layout},
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, List, ListItem, Paragraph},
    Frame, Terminal,
};
use std::io::{self, BufRead};
use std::sync::mpsc;
use std::time::Duration;

// ── colour palette (from spec) ────────────────────────────────────────────────
const SLATE: Color = Color::DarkGray;
const CREAM: Color = Color::White;
const EMERALD: Color = Color::Green;
const AMBER: Color = Color::Yellow;
const RUBY: Color = Color::Red;

// ── application state ─────────────────────────────────────────────────────────
struct AppState {
    events: Vec<AgentEvent>,
    scroll: usize,
    run_start: Option<String>,
}

impl AppState {
    fn new() -> Self {
        Self { events: Vec::new(), scroll: 0, run_start: None }
    }

    fn push(&mut self, ev: &AgentEvent) {
        if let AgentEvent::RunStart(rs) = ev {
            self.run_start = Some(format!(
                "{} / {} / max_steps:{}",
                rs.model, rs.provider, rs.max_steps
            ));
        }
        self.events.push(ev.clone());
        let len = self.events.len();
        if len > 0 {
            self.scroll = len.saturating_sub(1);
        }
    }
}

// ── colour helpers ────────────────────────────────────────────────────────────
fn event_style(ev: &AgentEvent) -> Style {
    match ev {
        AgentEvent::RunStart(_) | AgentEvent::RunEnd(_) => {
            Style::default().fg(EMERALD)
        }
        AgentEvent::RunError(_) => Style::default().fg(RUBY).add_modifier(Modifier::BOLD),
        AgentEvent::Think(_) | AgentEvent::Act(_) | AgentEvent::Observe(_) => {
            Style::default().fg(CREAM)
        }
        AgentEvent::Verify(_) | AgentEvent::FileEdit(_) | AgentEvent::Decide(_) => {
            Style::default().fg(AMBER)
        }
        AgentEvent::PermissionGate(_) => Style::default().fg(RUBY),
        AgentEvent::TokenUsage(_) | AgentEvent::StateUpdate(_) | AgentEvent::Converge(_) => {
            Style::default().fg(CREAM)
        }
    }
}

fn event_label(ev: &AgentEvent) -> &'static str {
    match ev {
        AgentEvent::RunStart(_) => "RunStart",
        AgentEvent::RunEnd(_) => "RunEnd",
        AgentEvent::RunError(_) => "RunError",
        AgentEvent::Think(_) => "Think",
        AgentEvent::Act(_) => "Act",
        AgentEvent::Observe(_) => "Observe",
        AgentEvent::Verify(_) => "Verify",
        AgentEvent::FileEdit(_) => "FileEdit",
        AgentEvent::TokenUsage(_) => "TokenUsage",
        AgentEvent::StateUpdate(_) => "StateUpdate",
        AgentEvent::Decide(_) => "Decide",
        AgentEvent::Converge(_) => "Converge",
        AgentEvent::PermissionGate(_) => "PermGate",
    }
}

fn event_summary(ev: &AgentEvent) -> String {
    match ev {
        AgentEvent::RunStart(rs) => format!("task: {}", rs.task),
        AgentEvent::RunEnd(re) => format!(
            "success:{} steps:{} tokens:{} cost:{:.4}",
            re.success, re.total_steps, re.total_tokens, re.total_cost
        ),
        AgentEvent::RunError(err) => format!("error: {}", err.error),
        AgentEvent::Think(t) => format!("{} tokens:{}", truncate(&t.thought, 60), t.tokens_used),
        AgentEvent::Act(a) => format!("action: {} tool:{}", truncate(&a.action, 30), a.tool_name),
        AgentEvent::Observe(o) => format!("obs: {} exit:{}", truncate(&o.observation, 50), o.exit_code),
        AgentEvent::Verify(v) => format!("gate:{} status:{}", v.gate, v.status),
        AgentEvent::FileEdit(fe) => format!("path:{} action:{}", fe.path, fe.action_type),
        AgentEvent::TokenUsage(tu) => {
            format!("tokens:{} cost:{:.4}", tu.total_tokens, tu.total_cost)
        }
        AgentEvent::StateUpdate(su) => {
            format!("key:{} -> {}", su.key, truncate(&su.new_value, 40))
        }
        AgentEvent::Decide(d) => {
            format!("dec:{} conf:{}", truncate(&d.decision, 30), d.confidence)
        }
        AgentEvent::Converge(c) => {
            format!("ok:{} ev:{}", c.converged, truncate(&c.evidence, 30))
        }
        AgentEvent::PermissionGate(pg) => {
            format!("action:{} verdict:{}", pg.action, pg.verdict)
        }
    }
}

fn truncate(s: &str, max: usize) -> String {
    if s.len() <= max {
        s.to_string()
    } else {
        format!("{}…", &s[..max])
    }
}

// ── UI rendering ──────────────────────────────────────────────────────────────
fn ui(f: &mut Frame, state: &AppState) {
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(1),
            Constraint::Min(0),
            Constraint::Length(1),
        ])
        .split(f.size());

    // breadcrumb
    let bread_text = match &state.run_start {
        Some(label) => format!(" RunStart → {} → Running…", label),
        None => " Forge TUI — awaiting events …".to_string(),
    };
    let bread_line =
        Line::from(Span::styled(bread_text, Style::default().fg(AMBER).bg(SLATE)));
    f.render_widget(bread_line, chunks[0]);

    // event log — build items in reverse (newest first)
    let items: Vec<ListItem> = state
        .events
        .iter()
        .rev()
        .map(|ev| {
            let label = event_label(ev);
            let summary = event_summary(ev);
            let style = event_style(ev);
            let line = Line::from(vec![
                Span::styled(format!(" {:<10}", label), style),
                Span::raw(" "),
                Span::styled(summary, style),
            ]);
            ListItem::new(line)
        })
        .collect();

    let list_area = chunks[1];
    let height = list_area.height.max(1) as usize;

    if !items.is_empty() {
        let total = items.len();
        let scroll_pos = state.scroll.min(total.saturating_sub(1));
        let start = scroll_pos;
        let end = (start + height).min(total);

        let display_items: Vec<ListItem> = if start < end {
            items[start..end].to_vec()
        } else {
            Vec::new()
        };

        let display_log = List::new(display_items)
            .block(Block::default().style(Style::default().bg(SLATE)));
        f.render_widget(display_log, list_area);
    } else {
        let empty = Paragraph::new("").style(Style::default().bg(SLATE));
        f.render_widget(empty, list_area);
    }

    // status bar
    let total = state.events.len();
    let latest_label = state.events.last().map(event_label).unwrap_or("—");
    let status = format!(
        " Events: {} | Latest: {} | [j/k] scroll  [q] quit ",
        total, latest_label
    );
    let status_line =
        Line::from(Span::styled(status, Style::default().fg(CREAM).bg(SLATE)));
    f.render_widget(status_line, chunks[2]);
}

// ── stdin reader ─────────────────────────────────────────────────────────────
fn spawn_stdin_reader(tx: mpsc::Sender<AgentEvent>) {
    std::thread::spawn(move || {
        let stdin = io::stdin();
        let reader = stdin.lock();
        for line in reader.lines() {
            match line {
                Ok(line) if !line.trim().is_empty() => {
                    if let Ok(ev) = serde_json::from_str::<AgentEvent>(&line) {
                        let _ = tx.send(ev);
                    }
                }
                _ => {}
            }
        }
    });
}

// ── entry point ───────────────────────────────────────────────────────────────
fn main() -> io::Result<()> {
    let (tx, rx) = mpsc::channel::<AgentEvent>();
    spawn_stdin_reader(tx);

    enable_raw_mode()?;
    let mut stdout = io::stdout();
    execute!(stdout, EnterAlternateScreen, EnableMouseCapture)?;
    let backend = CrosstermBackend::new(stdout);
    let mut terminal = Terminal::new(backend)?;

    let mut state = AppState::new();
    let tick_rate = Duration::from_millis(100);

    let res = run(&mut terminal, &mut state, &rx, tick_rate);

    disable_raw_mode()?;
    execute!(
        terminal.backend_mut(),
        LeaveAlternateScreen,
        DisableMouseCapture
    )?;
    terminal.show_cursor()?;

    res
}

fn run(
    terminal: &mut Terminal<CrosstermBackend<std::io::Stdout>>,
    state: &mut AppState,
    rx: &mpsc::Receiver<AgentEvent>,
    tick_rate: Duration,
) -> io::Result<()> {
    loop {
        terminal.draw(|f| ui(f, state))?;

        if event::poll(tick_rate)? {
            if let Event::Key(key) = event::read()? {
                match key.code {
                    KeyCode::Char('q') => break,
                    KeyCode::Char('j') => {
                        state.scroll = state.scroll.saturating_sub(1);
                    }
                    KeyCode::Char('k') => {
                        let max = state.events.len().saturating_sub(1);
                        state.scroll = (state.scroll + 1).min(max);
                    }
                    _ => {}
                }
            }
        }

        while let Ok(ev) = rx.try_recv() {
            state.push(&ev);
        }
    }

    Ok(())
}

