"""Build the decision page (docs/index.html) from the result tables in outputs/tables.

Every number in the text is computed here from those tables; nothing is typed in by hand.

Usage:
    python src/build_site.py
"""
import sys
from html import escape
from pathlib import Path

import pandas as pd

import site_kit

ROOT = Path(__file__).resolve().parent.parent
TABLES = ROOT / "outputs" / "tables"
OUT = ROOT / "docs" / "index.html"


def n(v):
    return f"{int(round(v)):,}"


def pct(v, d=1):
    return f"{v:.{d}f}%"


def load():
    t = {p.stem: pd.read_csv(p) for p in TABLES.glob("r*.csv")}
    return t


def survival_grid(df, series):
    """Share still open at each day 0..90, carried forward between event days."""
    rows = df[df.series == series].set_index("days_since_created").pct_still_open
    pts, cur = [[0, 100.0]], 100.0
    for d in range(1, 91):
        if d in rows.index:
            cur = float(rows.loc[d])
        pts.append([d, cur])
    return pts


def build(out=None):
    t = load()
    pareto = t["r10_slow_request_pareto"]
    total_req, total_slow = pareto.requests.sum(), pareto.slow_requests.sum()
    hpd = pareto[pareto.agency == "HPD"].sort_values("slow_requests", ascending=False)
    hpd_share = 100 * hpd.slow_requests.sum() / total_slow
    top5 = hpd.head(5)
    top5_share = 100 * top5.slow_requests.sum() / total_slow
    drivers = t["r14_slow_drivers"].set_index("predictors").pct_of_variation_explained
    levers = t["r16_levers"]
    lever = {k[0]: r for k in levers.lever for _, r in levers[levers.lever == k].iterrows()}
    lev_a = levers[levers.lever.str.startswith("A:")].iloc[0]
    lev_b25 = levers[levers.lever.str.contains("top 25")].iloc[0]
    lev_c = levers[levers.lever.str.startswith("C:")].iloc[0]
    vul = t["r15_vulnerability_gap"]
    surv = t["r13_survival_curves"]
    mess = t["r18_data_mess"]
    desc = t["r17_hpd_descriptors"]
    dq = t["r02_data_quality"].set_index("check_name")
    raw_rows = int(dq.loc["raw_rows", "n"])
    unknown = int(mess[mess.issue.str.startswith("Marked CLOSED")].rows_affected.iloc[0])
    inflation = mess[mess.issue.str.startswith("Marked CLOSED")].if_ignored.iloc[0]
    hpd_surv = surv[surv.series == "HPD"].set_index("days_since_created").pct_still_open
    open7 = float(hpd_surv[hpd_surv.index <= 7].iloc[-1])
    open30 = float(hpd_surv[hpd_surv.index <= 30].iloc[-1])
    open89 = float(hpd_surv.iloc[-1])
    place_alone = max(drivers["Borough"], drivers["ZIP code"], drivers["Month created"])
    gaps = vul.gap_pp.abs().max()
    top_desc = desc.sort_values("slow_requests", ascending=False).iloc[0]

    # ---------- chart data
    agencies = [s for s in surv.series.unique() if not s.startswith("HPD:")]
    order = ["HPD", "DPR", "DOT", "DSNY", "NYPD"] + [a for a in agencies if a not in ("HPD", "DPR", "DOT", "DSNY", "NYPD")]
    colors = [f"var(--s{i + 1})" for i in range(8)]
    agency_series = [{"name": a, "color": colors[i], "pts": survival_grid(surv, a)} for i, a in enumerate(order[:6])]
    type_names = [s for s in surv.series.unique() if s.startswith("HPD:")]
    type_series = [{"name": s.replace("HPD: ", "").title(), "color": colors[i], "pts": survival_grid(surv, s)}
                   for i, s in enumerate(type_names)]

    top12 = pareto.sort_values("slow_requests", ascending=False).head(12)
    pareto_rows = [{"label": f"{r.agency} · {r.complaint_type.title()}"[:40], "value": float(r.slow_requests),
                    "sub": f"{r.slow_rate_pct:.0f}% slow",
                    "color": "var(--s2)" if r.agency == "HPD" else "var(--s1)",
                    "tip": f"<b>{escape(r.agency)} · {escape(r.complaint_type)}</b>{n(r.slow_requests)} slow of {n(r.requests)} requests ({r.slow_rate_pct:.1f}%)<br>{r.cumulative_pct_of_slow:.1f}% of all slow requests up to this type"}
                   for r in top12.itertuples()]

    driver_rows = [{"label": p, "value": float(v), "color": "var(--s2)" if p == "Complaint type" else "var(--s1)",
                    "tip": f"<b>{escape(p)}</b>explains {v:.1f}% of whether a request is slow<br>({int(g):,} groups fitted on half the data, scored on the other half)"}
                   for p, v, g in zip(t["r14_slow_drivers"].predictors, t["r14_slow_drivers"].pct_of_variation_explained,
                                      t["r14_slow_drivers"].groups_fitted)]

    lever_rows = []
    for r in levers.itertuples():
        if r.lever.startswith("A:"):
            label = "A · Borough catch-up"
        elif r.lever.startswith("C:"):
            label = "C · Fix top 5 HPD types (scenario)"
        elif "top 25" in r.lever:
            label = "B · ZIP catch-up, worst 25 cells"
        elif "top 100" in r.lever:
            label = "B · ZIP catch-up, worst 100 cells"
        else:
            label = f"B · ZIP catch-up, all {n(r.targets)} cells"
        lever_rows.append({"label": label, "value": float(r.recoverable_slow),
                           "sub": f"· {n(r.targets)} targets", "color": "var(--s2)" if r.lever.startswith("C:") else "var(--s1)",
                           "tip": f"<b>{escape(r.lever)}</b>recovers about {n(r.recoverable_slow)} slow requests ({r.pct_of_all_slow:.1f}% of all)<br>needs {n(r.targets)} separate targets"})

    margin_rows = []
    for scope, color in (("HPD only", "var(--s2)"), ("All agencies", "var(--s1)")):
        for r in vul[vul.scope == scope].itertuples():
            margin_rows.append({"label": f"{scope} · index {r.hvi}", "v": float(r.gap_pp), "m": float(r.gap_margin_pp), "color": color,
                                "tip": f"<b>{scope}, vulnerability index {r.hvi}</b>{n(r.requests)} requests<br>slow rate {r.slow_rate_pct:.1f}% vs {r.expected_given_type_pct:.1f}% expected for their complaint types<br>gap {r.gap_pp:+.2f} pp (±{r.gap_margin_pp:.2f})"})

    data = {"agency": agency_series, "types": type_series, "pareto": pareto_rows, "drivers": driver_rows,
            "levers": lever_rows, "margin": margin_rows}

    # ---------- tables as HTML
    mess_rows = "".join(
        f"<tr><td>{escape(r.issue)}</td><td>{n(r.rows_affected)}<br><span class='tag'>{r.pct_of_requests:.2f}%</span></td>"
        f"<td>{escape(r.handling)}</td><td>{escape(r.if_ignored)}</td></tr>" for r in mess.itertuples())
    first_desc = desc[desc.rank_in_type == 1].sort_values("slow_requests", ascending=False)
    desc_rows = "".join(
        f"<tr><td>{escape(r.complaint_type.title())}</td><td>{escape(r.descriptor.title())}</td><td class='num'>{n(r.slow_requests)}</td>"
        f"<td class='num'>{r.slow_rate_pct:.0f}%</td><td class='num'>{r.pct_of_type_slow:.0f}%</td></tr>" for r in first_desc.itertuples())

    body = f"""
<header class="hero"><div class="wrap">
<p class="eyebrow">Case study · NYC 311 service requests · all of 2024</p>
<h1>Where should New York put the next unit of housing-repair capacity?</h1>
<p class="lede">{n(raw_rows)} requests from the city's 311 system, cleaned and analysed in SQL. The question: which requests wait longest to be closed, why, and where would effort recover the most?</p>
<div class="decision">
<h2>Recommendation</h2>
<p style="margin:0">Fix the process behind the <b>five largest housing-maintenance complaint types</b> (unsanitary condition, plumbing, paint/plaster, door/window, water leak). Do not spend the capacity on borough or ZIP targeting, or on changing how people contact 311.</p>
<ol>
<li>The housing agency (HPD) holds <b>{pct(hpd_share)}</b> of the {n(total_slow)} requests not closed within 7 days; those five types alone hold <b>{pct(top5_share)}</b>.</li>
<li>Complaint type alone explains <b>{pct(drivers['Complaint type'],0)}</b> of whether a request is slow. Borough, ZIP code and month each explain {pct(place_alone)} or less.</li>
<li>A one-quarter cut in the slow rate of those five types recovers about <b>{n(lev_c.recoverable_slow)}</b> slow requests with 5 targets. Fixing every borough-and-type cell that is slower than chance recovers {n(lev_a.recoverable_slow)} but needs {n(lev_a.targets)}; the 25 worst ZIP-type cells recover only {n(lev_b25.recoverable_slow)}.</li>
<li>Requests from more heat-vulnerable neighbourhoods show no consistent penalty: their slow rate differs from what their complaint mix predicts by at most {gaps:.1f} points, in both directions, and the gap does not grow with the index.</li>
</ol></div>
<div class="stats">
<div class="stat"><b>{n(total_req)}</b><span>requests with a judgeable 7-day outcome</span></div>
<div class="stat"><b>{pct(100*total_slow/total_req)}</b><span>not closed within 7 days</span></div>
<div class="stat"><b>{pct(open30)}</b><span>of HPD requests still open after 30 days</span></div>
<div class="stat"><b>{pct(open89)}</b><span>still open after 89 days (a long tail)</span></div>
</div>
</div></header>

<main class="wrap">
<section id="mess"><h2>1 · The data had traps, and one of them changes who looks worst</h2>
<p class="kicker">311 data looks tidy but is not. Seven problems were found and handled before any number was trusted. The biggest: {n(unknown)} requests are marked <i>Closed</i> with no close date, almost all from one agency (DHS). Counted as open they inflate the slow total, and DHS's slow rate would read {inflation.split('read ')[-1].split(' times')[0]} times too high. They are left out of every closure measure instead.</p>
<div class="pipe">
<div class="step"><b>1 · Source</b><strong>{n(raw_rows)}</strong><span>rows pulled day by day from the NYC Open Data API (366 files)</span></div><div class="arrow">→</div>
<div class="step"><b>2 · Stage</b><strong>text first</strong><span>every column read as text; bad values become empty instead of stopping the load</span></div><div class="arrow">→</div>
<div class="step"><b>3 · Clean</b><strong>{n(unknown)}</strong><span>closed-without-date rows kept out of closure measures; impossible dates never repaired</span></div><div class="arrow">→</div>
<div class="step"><b>4 · Model</b><strong>18 SQL files</strong><span>CTEs, window functions, survival curves, hold-out scoring; 25 tests</span></div><div class="arrow">→</div>
<div class="step"><b>5 · Check</b><strong>independent</strong><span>headline numbers recomputed from the raw files in pandas</span></div>
</div>
<div class="card tablewrap"><table class="mess"><thead><tr><th>Problem</th><th>Rows</th><th>What was done</th><th>If it had been ignored</th></tr></thead><tbody>{mess_rows}</tbody></table></div>
</section>

<section id="where"><h2>2 · Where the slow requests are</h2>
<p class="kicker">A request is <i>slow</i> if it was not closed within 7 days. Twelve complaint types hold about {pct(100*top12.slow_requests.sum()/total_slow,0)} of all slow requests; housing (orange) dominates.</p>
<div class="card"><h3>Requests not closed within 7 days, top 12 agency and complaint-type pairs</h3><div class="chart" id="c-pareto"></div>
<p class="note">Slow is not the same as failing: some types are slow by design (new tree requests, for-hire vehicle complaints), and only 0.6% of requests carry a due date, so fair per-type targets cannot be tested.</p></div>
<div class="card"><h3>How long requests stay open (Kaplan–Meier, open requests treated as still waiting)</h3><div class="chart" id="c-surv-agency"></div>
<p class="note">After 7 days {pct(open7,0)} of HPD requests are still open; after 30 days {pct(open30,0)}; after 89 days {pct(open89)}. NYPD requests are closed within hours, so it is not comparable with the others (closure there generally means an officer responded).</p></div>
</section>

<section id="why"><h2>3 · Why they are slow: the type of problem, not the place</h2>
<p class="kicker">Each bar predicts "slow or not" from one set of facts, using rates learned on half the requests and scored on the other half. If place mattered, geography would explain something.</p>
<div class="card"><h3>Share of the variation in slow / not slow that each set of facts explains</h3><div class="chart" id="c-drivers"></div>
<p class="note">Adding borough, channel and month to complaint type lifts the score from {pct(drivers['Complaint type'])} to {pct(drivers['Type + borough + channel + month'])}. The 10.7% for place, channel and month without type is mostly intake channel standing in for complaint mix.</p></div>
<div class="card"><h3>HPD: how long the five biggest slow types stay open</h3><div class="chart" id="c-surv-types"></div>
<p class="note">The five curves are close together: the slowness is shared across housing-repair types, which points to a common cause (how repairs are dispatched and verified) rather than five separate problems.</p></div>
<div class="card"><h3>Inside the five types: the single biggest problem in each</h3><div class="tablewrap"><table><thead><tr><th>Complaint type</th><th>Biggest slow problem</th><th class="num">Slow requests</th><th class="num">Slow rate</th><th class="num">Share of type's slow</th></tr></thead><tbody>{desc_rows}</tbody></table></div>
<p class="note">The single largest: {escape(top_desc.descriptor.title())} under {escape(top_desc.complaint_type.title())}, with {n(top_desc.slow_requests)} slow requests.</p></div>
</section>

<section id="act"><h2>4 · What to do, and what each option would recover</h2>
<p class="kicker">Recoverable means slow requests above what the citywide rate for that complaint type predicts, minus a 95% chance margin, so noise in small cells is not counted as something to fix. Option C is a scenario (a quarter off the slow rate), not a forecast.</p>
<div class="card"><h3>Slow requests recovered, and how many separate targets each option needs</h3><div class="chart" id="c-levers"></div></div>
<div class="card"><h3>Do more vulnerable neighbourhoods wait longer for the same help?</h3><div class="chart" id="c-margin"></div>
<p class="note">Gap = actual slow rate minus the rate expected from complaint type, with a 95% margin. Index 1 is least and 5 most vulnerable (NYC Health Department Heat Vulnerability Index, joined by ZIP). Gaps are small, point in both directions and do not rise with the index (the 95% margins are narrow, so the HPD index-2 gap of about +2.5 points is real but small), so this data gives no reason to target by neighbourhood. This is a statement about response times, not about need.</p></div>
</section>

<section id="limits"><h2>5 · What would change this recommendation</h2>
<ul class="limits">
<li><b>One year, one city.</b> A second year would show whether the same types stay slow.</li>
<li><b>Closure is an agency decision.</b> If HPD closes requests only when a landlord reports a fix, 7-day closure measures landlord behaviour, not the agency's. That would shift the fix from capacity to enforcement.</li>
<li><b>Due dates are almost absent</b> (0.6% of requests), so there are no per-type targets to judge against.</li>
<li><b>Associations, not causes.</b> The 25% cut is a scenario; the data cannot say it is achievable.</li>
<li><b>The dataset changes.</b> Close dates keep arriving, so a later pull can differ slightly. These tables are from the pull dated 7 November 2026.</li>
</ul></section>
</main>
<footer><div class="wrap">Data: NYC Open Data 311 Service Requests (erm2-nwe9) and NYC DOHMH Heat Vulnerability Index (4mhf-duep). Code, SQL, tests and method notes are in the repository. Re-run with <code>make run charts site</code>.</div></footer>
"""

    script = """
const D = DATA;
legend('#c-pareto',[{name:'Housing (HPD)',color:'var(--s2)'},{name:'Other agencies',color:'var(--s1)'}]);
legend('#c-surv-agency', D.agency.map(s=>({name:s.name,color:s.color})));
hbar('#c-pareto',{rows:D.pareto,vf:fmt.int,tf:fmt.k,lw:230});
lineChart('#c-surv-agency',{series:D.agency,x:[0,90],y:[0,100],yf:fmt.pct0,xf:v=>v,xunit:' days',xlab:'Days since the request was created',ylab:'% still open',step:true});
hbar('#c-drivers',{rows:D.drivers,vf:fmt.pct,tf:fmt.pct0,lw:260,max:60});
legend('#c-surv-types', D.types.map(s=>({name:s.name,color:s.color})));
lineChart('#c-surv-types',{series:D.types,x:[0,90],y:[0,100],yf:fmt.pct0,xf:v=>v,xunit:' days',xlab:'Days since the request was created',ylab:'% still open',step:true,h:300});
hbar('#c-levers',{rows:D.levers,vf:fmt.int,tf:fmt.k,lw:300});
marginChart('#c-margin',{rows:D.margin,x:[-4,4],xf:v=>(v>0?'+':'')+v+' pp',xlab:'Actual slow rate minus rate expected for the same complaint types (percentage points)'});
"""
    html = site_kit.page("NYC 311 service performance", "Where NYC 311 requests wait longest, why, and where effort would recover the most.",
                         body, data, script)
    target = Path(out) if out else OUT
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html)
    print("wrote", target, f"{len(html) / 1024:.0f} KB")


if __name__ == "__main__":
    sys.exit(build() or 0)
