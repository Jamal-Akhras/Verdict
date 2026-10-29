"""Canned outputs for demo mode. Realistic enough to demo the full product
with zero AI spend. Keyed by a marker found in each agent's system prompt."""

INTAKE = {
    "normalized_brief": "A web app for boutique gyms (5-50 classes/week) to manage class schedules, member bookings, and payments - replacing WhatsApp threads and spreadsheets with a booking page, trainer dashboard, and Stripe payments.",
    "target_user": "Owners of small boutique gyms and fitness studios",
    "problem": "Bookings are managed through WhatsApp and spreadsheets: double bookings, no-shows, unpaid sessions, and hours of admin every week.",
    "assumptions": [
        "Gym owners will pay a monthly subscription if it saves admin time",
        "Members will book via a web link without a native app",
        "Stripe is acceptable for payments in the target market",
    ],
    "missing_info": ["Monthly budget", "Target country/currency", "Launch timeline"],
    "follow_up_questions": [
        "What is your budget for building and running this?",
        "Which country or market are you targeting first?",
        "Do you want to validate demand first or build straight away?",
    ],
}

FEASIBILITY = {
    "verdict": "validate",
    "confidence": 72,
    "scores": [
        {"category": "customer_pain", "score": 8, "weight": 20, "reasoning": "Admin overhead is a daily, felt pain for small gym owners."},
        {"category": "reachable_buyer", "score": 7, "weight": 15, "reasoning": "Local gyms are identifiable and reachable via direct outreach."},
        {"category": "build_feasibility", "score": 8, "weight": 15, "reasoning": "Standard CRUD + payments; well within AI-assisted build range."},
        {"category": "monetization_clarity", "score": 7, "weight": 15, "reasoning": "Clear subscription model with per-location pricing."},
        {"category": "competitive_gap", "score": 5, "weight": 10, "reasoning": "Mindbody/Glofox dominate mid-market; the low end is underserved but crowded with point tools."},
        {"category": "market_size", "score": 6, "weight": 10, "reasoning": "Large number of small studios, but low willingness to pay per unit."},
        {"category": "founder_fit", "score": 6, "weight": 10, "reasoning": "Solo non-technical founder fits a narrow-wedge SaaS."},
        {"category": "risk_compliance", "score": 7, "weight": 5, "reasoning": "Payments and member data need care but are standard."},
    ],
    "reasoning": "The pain is real and the build is feasible, but the market is crowded at the top. The winning wedge is boutique gyms still on WhatsApp and spreadsheets - validate that they will switch and pay before building.",
    "mvp_scope": ["Class schedule page", "Member booking flow", "Trainer dashboard", "Stripe payments", "Admin calendar"],
    "do_not_build": ["Native mobile app", "Advanced analytics", "Full CRM", "AI workout planner"],
    "assumptions": ["10+ gyms will pre-commit at $49/mo", "Owners switch off WhatsApp if setup takes <1 hour", "No-show fees are a compelling hook"],
    "validation_plan": ["Interview 10 boutique gym owners about booking admin", "Landing page with $49/mo pricing and waitlist", "3 pre-orders or LOIs before building"],
}

RESEARCH = {
    "competitors": [
        {"name": "Mindbody", "description": "Market-leading wellness booking platform", "pricing_estimate": "$139-$699/mo (estimate)", "gap": "Too expensive and heavy for small boutique gyms"},
        {"name": "Glofox", "description": "Gym management software", "pricing_estimate": "$100+/mo (estimate)", "gap": "Onboarding and contracts aimed at bigger studios"},
        {"name": "Momence", "description": "Booking + payments for classes", "pricing_estimate": "$49-$399/mo (estimate)", "gap": "Broad feature set; not focused on the WhatsApp-replacement niche"},
        {"name": "Calendly + Stripe links", "description": "DIY stack many small gyms improvise", "pricing_estimate": "$0-$20/mo", "gap": "No member management, no class capacity, no no-show handling"},
    ],
    "demand_signals": ["Small gyms commonly coordinate bookings via WhatsApp groups", "Owner communities complain about no-shows and unpaid sessions", "Incumbent pricing pushes small studios to spreadsheets"],
    "customer_segments": ["Boutique fitness studios (yoga, pilates, HIIT)", "Independent personal trainers with group classes", "Climbing/box gyms with class caps"],
    "memo": "The mid-market is locked up by Mindbody and Glofox, but their pricing and complexity leave a real gap under ~$50/mo. The practical competitor is not software - it is WhatsApp plus a spreadsheet. Positioning should be 'replace the group chat', not 'cheaper Mindbody'.",
    "research_gaps": ["Confirm current pricing pages (no live web access in demo mode)", "Validate churn drivers for Glofox at the low end", "Country-specific payment preferences"],
}

FINANCE = {
    "pricing_recommendation": {"model": "subscription", "price_point_usd": 49, "rationale": "$49/mo per location: well under incumbent entry pricing; maps to hours of admin saved weekly."},
    "scenarios": [
        {"case": "worst", "monthly_revenue_usd": 245, "key_driver": "5 gyms x $49: slow direct sales, high churn"},
        {"case": "base", "monthly_revenue_usd": 980, "key_driver": "20 gyms x $49: steady local outreach + referrals"},
        {"case": "best", "monthly_revenue_usd": 4900, "key_driver": "100 gyms x $49: community-led growth in one metro"},
    ],
    "breakeven": {"units_needed": 4, "assumption": "~$180/mo infra + AI costs at small scale"},
    "cost_drivers": ["Hosting and database", "Stripe fees (~2.9%)", "AI usage for support/content", "Founder time on onboarding"],
    "assumptions": ["Churn under 4%/mo", "CAC near zero via direct outreach", "No paid ads in year one", "All figures are illustrative estimates, not forecasts"],
}

PRD = {
    "overview": "A booking web app for boutique gyms that replaces WhatsApp-and-spreadsheet coordination: owners publish a class schedule, members book and pay online, trainers see their day at a glance.",
    "user_stories": [
        {"title": "Publish class schedule", "story": "As a gym owner, I want to publish my weekly class schedule, so that members always see current availability.", "acceptance_criteria": ["Owner can create/edit/delete classes with capacity", "Schedule visible on a public page", "Changes reflect immediately"], "priority": "P0"},
        {"title": "Book a class", "story": "As a member, I want to book a spot in a class, so that my place is guaranteed.", "acceptance_criteria": ["Booking decrements capacity atomically", "Member gets confirmation email", "Full classes show a waitlist option"], "priority": "P0"},
        {"title": "Pay for a class pack", "story": "As a member, I want to buy a class pack online, so that I do not handle cash at the desk.", "acceptance_criteria": ["Stripe checkout for packs", "Credits decrement per booking", "Owner sees payment status"], "priority": "P0"},
        {"title": "Trainer day view", "story": "As a trainer, I want to see who is booked into my classes today, so that I can plan sessions.", "acceptance_criteria": ["Read-only roster per class", "No-shows markable in one tap"], "priority": "P1"},
        {"title": "Cancel a booking", "story": "As a member, I want to cancel within the policy window, so that my credit is returned.", "acceptance_criteria": ["Policy window configurable by owner", "Late cancellations forfeit credit"], "priority": "P1"},
    ],
    "non_goals": ["Native mobile apps", "Payroll or staff scheduling", "Nutrition/workout content", "Multi-location franchises"],
    "success_metrics": ["Bookings per gym per week", "% of bookings paid online", "Owner admin hours saved (self-reported)", "Churn under 4%/mo"],
    "open_questions": ["Waitlist auto-promotion rules", "Refund policy defaults per market"],
}

QA_REPORT = {
    "findings": [
        {"section": "user_stories/Book a class", "issue": "No story covers double-booking the same member into one class", "severity": "medium"},
        {"section": "user_stories/Pay for a class pack", "issue": "Acceptance criteria do not cover failed payment recovery", "severity": "medium"},
        {"section": "success_metrics", "issue": "'Admin hours saved' is self-reported and unmeasurable in-product", "severity": "low"},
    ],
    "recommendation": "pass",
    "summary": "Solid, tightly-scoped PRD. Two medium gaps around booking edge cases and payment failure should be added to acceptance criteria before build, but nothing blocks approval.",
}

TECH = {
    "stack": [
        {"layer": "frontend", "choice": "Next.js + TypeScript", "alternative_considered": "Vite + React", "justification": "SSR for the public schedule page, huge ecosystem, AI tools know it well"},
        {"layer": "backend", "choice": "Next.js API routes", "alternative_considered": "Separate FastAPI service", "justification": "One deployable for a solo founder; split later if needed"},
        {"layer": "database", "choice": "Postgres (Neon)", "alternative_considered": "SQLite", "justification": "Relational fits bookings/capacity; Neon free tier to start"},
        {"layer": "payments", "choice": "Stripe Checkout + webhooks", "alternative_considered": "Paddle", "justification": "Best docs, class-pack model maps to products/prices"},
        {"layer": "auth", "choice": "Clerk", "alternative_considered": "NextAuth", "justification": "Fastest safe path to member + owner roles"},
        {"layer": "hosting", "choice": "Vercel", "alternative_considered": "Railway", "justification": "Free tier, zero-ops for Next.js"},
    ],
    "data_model": [
        {"entity": "Gym", "purpose": "One paying location", "key_fields": ["name", "owner_id", "cancellation_window_hours"]},
        {"entity": "ClassSession", "purpose": "A scheduled class with capacity", "key_fields": ["gym_id", "trainer_id", "starts_at", "capacity"]},
        {"entity": "Booking", "purpose": "A member's reserved spot", "key_fields": ["session_id", "member_id", "status", "credit_id"]},
        {"entity": "CreditPack", "purpose": "Prepaid class credits", "key_fields": ["member_id", "gym_id", "credits_total", "credits_used"]},
    ],
    "api_surface": [
        {"method": "GET", "path": "/api/gyms/{id}/schedule", "purpose": "Public schedule"},
        {"method": "POST", "path": "/api/sessions/{id}/bookings", "purpose": "Book a spot (atomic capacity check)"},
        {"method": "POST", "path": "/api/checkout", "purpose": "Start Stripe checkout for a pack"},
        {"method": "POST", "path": "/api/webhooks/stripe", "purpose": "Payment confirmation"},
    ],
    "security_flags": [
        {"component": "Stripe webhooks", "risk": "Spoofed payment confirmations", "mitigation": "Verify webhook signatures; never trust client-side success"},
        {"component": "Booking endpoint", "risk": "Race conditions oversell capacity", "mitigation": "Row-level locking or serializable transaction on capacity check"},
        {"component": "Member data", "risk": "Cross-gym data exposure", "mitigation": "Every query scoped by gym_id; tested authorization middleware"},
    ],
    "adrs": [
        {"decision": "Single Next.js app over frontend+API split", "reason": "Solo founder velocity; revisit at 50+ gyms"},
        {"decision": "Credits model over per-class payments", "reason": "Fewer Stripe transactions, matches gym pack conventions"},
    ],
    "build_order": ["Schema + migrations", "Auth + gym onboarding", "Schedule CRUD", "Booking flow with capacity", "Stripe packs + webhooks", "Trainer day view", "Cancellation policy"],
}

SECURITY = {
    "findings": [
        {"category": "payments", "severity": "high", "finding": "Stripe webhook handler is the single source of payment truth; unverified signatures would allow forged credits", "recommendation": "Verify Stripe-Signature on every webhook; reject and log failures"},
        {"category": "auth", "severity": "medium", "finding": "Trainer role must not access billing or member payment data", "recommendation": "Role checks on every API route, not just UI hiding"},
        {"category": "data", "severity": "medium", "finding": "Public schedule page must not leak member names on rosters", "recommendation": "Roster endpoints require trainer/owner auth; public page shows counts only"},
        {"category": "infra", "severity": "low", "finding": "No rate limiting on booking endpoint", "recommendation": "Add per-IP rate limits before launch"},
    ],
    "launch_checklist": [
        {"item": "Stripe webhook signature verification tested", "required_before_launch": True},
        {"item": "Authorization middleware covers all /api routes", "required_before_launch": True},
        {"item": "Booking capacity race condition test passes", "required_before_launch": True},
        {"item": "Rate limiting on auth + booking endpoints", "required_before_launch": True},
        {"item": "Backups enabled on Postgres", "required_before_launch": False},
    ],
    "go_no_go": "no_go",
    "summary": "Nothing exotic, but two things must be fixed before real money flows: webhook signature verification and strict role checks. Both are hours of work, not weeks. Do not launch payments until the checklist's required items pass.",
}

BACKLOG = {
    "tickets": [
        {"id": "T1", "title": "Project scaffold + schema", "objective": "Create Next.js app, Postgres schema, and migrations for Gym, ClassSession, Booking, CreditPack", "non_goals": ["Any UI polish"], "acceptance_criteria": ["Migrations apply cleanly", "Seed script creates a demo gym"], "test_requirements": ["Model constraint tests"], "depends_on": [], "estimated_size": "M"},
        {"id": "T2", "title": "Auth + roles", "objective": "Clerk auth with owner/trainer/member roles and route protection", "non_goals": ["Social logins"], "acceptance_criteria": ["Role-gated API middleware", "Unauthorized requests return 403"], "test_requirements": ["Authorization tests per role"], "depends_on": ["T1"], "estimated_size": "M"},
        {"id": "T3", "title": "Schedule CRUD", "objective": "Owner can create/edit classes; public schedule page renders availability", "non_goals": ["Recurring class templates"], "acceptance_criteria": ["Capacity shown", "Public page needs no auth"], "test_requirements": ["CRUD + public view tests"], "depends_on": ["T2"], "estimated_size": "M"},
        {"id": "T4", "title": "Booking flow", "objective": "Member books a spot; capacity decrements atomically; confirmation email", "non_goals": ["Waitlists"], "acceptance_criteria": ["No oversell under concurrent bookings", "Email sent"], "test_requirements": ["Concurrency test on capacity"], "depends_on": ["T3"], "estimated_size": "L"},
        {"id": "T5", "title": "Stripe class packs", "objective": "Checkout for credit packs; webhook credits the member; bookings consume credits", "non_goals": ["Subscriptions"], "acceptance_criteria": ["Signature-verified webhook", "Credits decrement per booking"], "test_requirements": ["Webhook signature test", "Credit consumption test"], "depends_on": ["T4"], "estimated_size": "L"},
        {"id": "T6", "title": "Trainer day view", "objective": "Read-only roster per class with no-show marking", "non_goals": ["Trainer messaging"], "acceptance_criteria": ["Roster requires trainer auth", "No-show persists"], "test_requirements": ["Role access test"], "depends_on": ["T4"], "estimated_size": "S"},
        {"id": "T7", "title": "Cancellation policy", "objective": "Members cancel within the owner-configured window; late cancels forfeit credit", "non_goals": ["Refunds to card"], "acceptance_criteria": ["Window enforced server-side", "Credit returned when eligible"], "test_requirements": ["Boundary tests on the window"], "depends_on": ["T5"], "estimated_size": "M"},
    ],
    "build_sequence_note": "Strict vertical slices: schema, auth, schedule, booking, payments. Payments (T5) is deliberately after booking works with free classes - it isolates Stripe risk from booking-logic risk. T6/T7 can run in parallel after T4/T5.",
}

SUPERVISOR_REVIEW = {
    "decision": "accept",
    "summary": "Draft covers the task requirements and stays inside the approved MVP scope.",
    "feedback": "",
    "issues": [
        {"severity": "low", "issue": "A few estimates are stated without a source", "where": "assumptions"},
    ],
    "escalation_title": "",
    "escalation_detail": "",
}

ESCALATION_TRIAGE = {
    "decision": "resolve",
    "rationale": "The open question is a quality judgement within the approved scope, not a founder decision.",
    "resolution": "Proceed with the draft as submitted; downstream agents should treat the flagged estimates as assumptions to validate.",
    "question": "",
    "severity": "low",
}

# Supervision markers come first: a supervisor's prompt can mention the
# worker it reviews, and must still get the supervisor fixture.
MARKERS = [
    ("Verdict Supervisor Review", SUPERVISOR_REVIEW),
    ("Verdict Escalation Triage", ESCALATION_TRIAGE),
    ("Founder Intake Agent", INTAKE),
    ("Feasibility Analyst", FEASIBILITY),
    ("Market Research Agent", RESEARCH),
    ("Finance/ROI Agent", FINANCE),
    ("Product Agent", PRD),
    ("CTO/Architecture Agent", TECH),
    ("Engineering Planner", BACKLOG),
    ("QA Agent", QA_REPORT),
    ("Security Review Agent", SECURITY),
]
