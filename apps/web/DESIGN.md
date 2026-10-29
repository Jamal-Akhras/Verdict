# Verdict design system (v0)

Direction: hybrid of "calm workspace" (light, uncluttered, approval inbox) and
"boardroom" (staff-card agents, departments, decisions "on your desk").
End users are often non-technical: plain language, one accent action per view,
progressive disclosure — details live in the drawer, not on the canvas.

## Tokens (Tailwind)

- Canvas: `stone-50` page, `white` cards/headers, `stone-200` borders
- Text: `stone-900` primary, `stone-500` secondary/minimum for content;
  `stone-400` only for true decoration (timestamps, bullet marks)
- Type floor: `text-xs` (12px) — never `text-[10px]`/`text-[11px]`
- Primary action: `stone-900` filled button (one per view)
- Stage chip: `blue-50/blue-700`
- Status: active `emerald`, completed `violet`, approved `sky`, paused/warning `amber`,
  blocked `rose`, proposed/archived `stone` — single source of truth in `lib/status.ts`
- Approval cards: blocking = `amber-300` border (urgent), non-blocking = `stone-200`
- Team avatar colors: Strategy `violet`, Product `orange`, Engineering `blue`,
  Quality `teal`, Governance `stone`
- Radius: `rounded-xl` cards/nodes, `rounded-lg` buttons, `rounded-full` chips/avatars

## Component inventory and roles

- `agents/AgentRoster` — default view: staff cards grouped by team, needs-you
  and working agents first, plus a status strip; `RosterTreeToggle` switches views
- `tree/AgentTree` — React Flow canvas behind the "Tree" tab
- `tree/AgentNode` — boardroom staff card: initials avatar, status chip,
  current task, model + spend line, budget bar (amber ≥80%)
- `agents/AgentDrawer` — full agent dossier in the right panel; "Ask why" first action
- `approvals/NeedsYou` — default right-panel content: "On your desk" decision
  cards (Approve / Request changes / Ask why) + dissent log
- `agents/AgentConfig` — "Setup" section inside the drawer: model, reports-to, send-backs,
  sign-off override, extra instructions
- `agents/TeamSetup` — right-panel "Team setup": hierarchy preset + instructions for every agent
- `app/settings/models` — model profiles (local / subscription / API), access chips:
  local `emerald`, subscription `violet`, API `sky`
- `app/projects/[id]/trace` — full prompt/review/escalation timeline grouped by task;
  role chips: draft `stone`, review `sky`, escalation `violet`
- Right panel is contextual: NeedsYou by default, AgentDrawer when a node is selected,
  TeamSetup from the header

## shadcn/ui adoption map (when installed)

Button, Badge, Card, Progress, Sheet (drawer on mobile), Dialog (Agent Builder),
Tooltip (explain statuses/authority in plain language), Tabs (drawer sections),
Accordion (feasibility evidence expanders), Sonner (toasts for audit events).

## Voice

Sentence case. Plain words over jargon ("On your desk", not "Pending approvals
queue"). Always show cost next to AI work. Every claim links to its source.
