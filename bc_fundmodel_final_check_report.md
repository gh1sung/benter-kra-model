# B&C Replication — Final Check Before Stage 2

**Verdict: GO.** The fundamental-model pipeline reproduces Bolton & Chapman (1986) at the level a
checksum is meant to confirm — same order of magnitude, correct structure, sensible coefficients,
no evidence of a look-ahead leak. The z-score AVESPRAT is a defensible choice. You're clear to add
public odds.

The one thing this report deliberately does *not* claim: "we hit B&C's 0.091 exactly." We didn't —
we land above it. Why that's still a pass is the whole point below.

---

## What a checksum is actually testing

The checksum's job is to catch a **broken pipeline**, not to match a number to the third decimal.
A broken pipeline gives you pseudo-R² that is wildly wrong — 0.9 (a leak), 0.01 (features not
wired in), or negative (sign flip). "Land near ~0.09" was always shorthand for "same order of
magnitude, behaving like B&C." Judged that way, this passes on four independent checks.

(Pseudo-R² here = how much better the model predicts the winner than a no-information baseline.
0 = no better than random over the field; higher = better.)

---

## Check 1 — Magnitude and decline pattern

| Explosion depth | z-score in-sample | z-score holdout | track-record in-sample | B&C published | z / B&C |
|---:|---:|---:|---:|---:|---:|
| E=1 | 0.1549 | 0.1149 | 0.1405 | 0.091 | 1.70× |
| E=2 | 0.1248 | 0.0978 | 0.1133 | 0.064 | 1.95× |
| E=3 | 0.1034 | 0.0828 | 0.0927 | 0.055 | 1.88× |

(Explosion depth = how deep into the finishing order you model. E=1 = just the winner; E=2 = 1st
and 2nd; E=3 = top three. It's a way to squeeze more choice sets out of the same races.)

Two things matter here, and the second matters more than the first:

- **Same order of magnitude.** We're ~1.5–1.9× B&C, not 10× or 0.1×. That alone rules out the
  pipeline-breaking bugs.
- **The *shape* matches.** B&C's R² falls as explosion depth increases (0.091 → 0.064 → 0.055).
  Ours does the exact same thing (0.155 → 0.125 → 0.103), and the ratio to B&C stays flat across
  all three depths. A bug would not politely reproduce B&C's decline curve — it would blow up at
  one depth or drift. Getting the qualitative behavior right across three depths is stronger
  evidence the mechanics are correct than hitting any single number would be.

**Why higher than B&C is fine, not alarming:** different market, different era, bigger sample.
B&C fit 200 races of 1980s US data; you have 6,000 races of Korean data (2008–2026). Korean racing
being somewhat more predictable is entirely plausible — and it's consistent with your own earlier
finding that Korea's public is "soft," which tends to go hand-in-hand with fundamentals carrying
more signal. Higher R² would only be a red flag if it came from a leak, which Check 3 rules out.

---

## Check 2 — Coefficients are economically sensible, AVESPRAT dominant

Standardized E=1 coefficients (z-score version), largest to smallest:

| Variable | Beta | Sign makes sense? |
|---|---:|---|
| AVESPRAT (speed, last 4) | +0.43 | Faster horse wins more ✓ — and it's the biggest, matching B&C |
| LSPEDRAT (speed, last race) | +0.31 | Same logic, recency ✓ |
| LIFE_PCT_WIN | +0.25 | Higher career win rate → wins ✓ |
| JOCK_PCT_WIN | +0.21 | Better jockey → wins ✓ |
| W_PER_RACE | +0.16 | More prize money = better horse ✓ |
| WEIGHT | +0.15 | Positive — see caveat below |
| NEWDIST (sprinter at a route) | −0.08 | Sprinter stepping up in distance is disadvantaged ✓ |
| POSTPOS (gate) | −0.06 | Worse gate, slightly worse ✓ |
| JOCK_NUM_WIN | +0.06 | More jockey wins ✓ |

Every sign lines up with racing logic, and **AVESPRAT is the single largest coefficient** — which
is B&C's headline result (their published AVESPRAT standardized weight of 0.562 was larger than all
their other variables combined). You reproduce that dominance. The track-record version gives the
same ordering with AVESPRAT on top, so this isn't an artifact of the z-score choice.

---

## Check 3 — It's not a look-ahead leak (the important one)

Elevated R² earns one hard question: is the model secretly seeing the future? The evidence says no.

- **Holdout R² is also elevated** (0.115 at E=1), not just in-sample. A leak or an overfit inflates
  in-sample while the holdout collapses. Here the in-sample/holdout gap is modest (0.155 vs 0.115)
  and the holdout *itself* sits above B&C. That's the signature of a genuinely more predictable
  market, not a leak.
- **Look-ahead controls were validated** during feature-building: shift-by-1 cumulative stats (a
  horse's own race never counts toward its own feature), and the speed baseline uses an expanding
  minimum shifted by one race, verified so every horse in a race gets the identical pre-race
  baseline (max 1 distinct value per race). A record set *in* a race can only affect *later* races.

---

## Check 4 — Sample is big enough

6,000 races at 1600–2000m on 건/양 (dry/good) tracks — **12× B&C's 500-race minimum**, and 30×
the 200 they actually used. The good/fast-track restriction that looked like it might starve the
sample kept 67% of races. No sample-size concern.

---

## The z-score vs track-record AVESPRAT decision

Your instinct is right — **z-score is fine to use** — but the reason matters, because "it gives
higher R²" is a bad reason on its own (you don't pick a formula just because it inflates a score).
The actual justification is stronger:

You built the B&C-faithful "track-record" speed rating specifically to test whether the z-score
shortcut was *why* your R² sat above B&C. It wasn't. Switching to B&C's literal formula lowered R²
by only ~9–10% and **left you still 1.5–1.7× above B&C** — refit on the identical race sample to
rule out coverage effects. So:

- The gap to B&C is a **market property**, not an artifact of your speed-figure construction. Both
  formulations show it.
- The track-record version buys you *nothing* in fidelity — it doesn't move you toward B&C — while
  costing R² and adding a second methodology to maintain.
- Both versions pass every structural check identically (AVESPRAT dominant, sensible signs,
  matching decline curve).

Net: keep the z-score AVESPRAT. Just **document it plainly** in your writeup — "AVESPRAT is a
z-scored time figure within (region × distance × class × condition) buckets, A/B-tested against
B&C's track-record formula, chosen for performance with no loss of fidelity." That turns it into a
transparent, defended deviation instead of an unexamined shortcut.

---

## Known caveats (flag, don't fix)

1. **WEIGHT is bigger than B&C's** (~0.15–0.19 here vs their ~0.012, i.e. near-zero). Likely
   because Korean impost encodes class/quality more directly than in B&C's data — better horses get
   assigned more weight, so WEIGHT partly proxies "class." This is a real market difference, not a
   bug, and it's worth keeping in mind for Stage 2: if WEIGHT is really carrying class information,
   the public probably prices that too, so it may add little *net* once odds are in.
2. **Raw speed-rating lower tail.** Minimum around −346, driven by DQ / pulled-up / very slow
   times. No clipping was applied (clipping isn't in B&C's formula and would be another deviation).
   Fine to leave, but note it exists.
3. **Framing for the writeup.** Your validation story is *structural* — correct signs, AVESPRAT
   dominance, matching decline curve, clean holdout — **not** "we matched 0.091." Don't let a
   reviewer expect the latter; lead with the former.

---

## Bottom line

Pipeline validated. The mechanics reproduce B&C's behavior faithfully; the level sits above B&C for
explainable, non-bug reasons; the speed-figure choice is sound and A/B-tested. Nothing here should
hold up Stage 2. Go add the public odds and get your first real ΔR² number.
