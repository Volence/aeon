# SIGIL-DECOUPLE — the joint re-plan, steps 1-4

**Status: PLAN ONLY. No bytes have moved and none may until the owner rules on the shape.**
Written 2026-08-27 jointly by the aeon and sigil overseers. The owner ruled the project a yes
and ruled the four-step sequence; what follows is the plan for executing it, not a re-opening
of that decision.

## Where it actually stands (measured, not read off a board)

| step | owner | state |
|---|---|---|
| 1. Cut the golden cord — sigil vendors a pinned aeon snapshot; drift detection becomes a nightly NON-BLOCKING job against CRCs aeon commits for itself | sigil | not started |
| 2. Placement authority comes home — anchors declared in `map.toml`, everything else placed fresh, an aeon-side gate asserting anchors and room | aeon | **HALF DONE** |
| 3. Retire `repin`/`pins.rs` from the landing path into an internal regression tool | sigil | not started |
| 4. Archive the byte-identical certification as a dated historical result | empyrean/sigil | not started, and **should wait for data** — see §3 |

### ⚠ Step 2 is HALF done, and the missing half is the half it is named for

Both lanes were treating step 2 as complete because the ROM re-layout landed (`c3f5cbe0`,
paired with sigil chain 168). It is not.

- **Landed**: the arrangement — banks after data by rule, 12,288 B animation room guaranteed in
  every shape, anchors written into `map.toml`.
- **NOT landed**: the authority. `docs/DEFERRED_WORK.md:10714` — *"The FROZEN TABLES are the
  placement authority, not `map.toml`"* — and `:10774`, *"under `SizeSource::Frozen` map.toml
  anchors are COSMETIC … the table island rows move the bytes."* **The arrangement moved home;
  the authority did not.**
- **NOT landed**: the aeon-side gate. Checked rather than assumed — **room**: `tools/bganim_room.py`
  has a `--gate` mode but `build.sh:224` prints *"bganim_room (the BG-anim ceiling is NOT
  checked)"* on at least one path, and that is one ceiling rather than the room guarantees
  plural. **Anchors**: nothing aeon-side asserts them; every `$48000` occurrence in `build.sh`
  and `tools/` is a comment or a derivation. **Four mentions, zero assertions.**

### ⚠ AMENDED SAME DAY — the boundary is NARROWER than "the tables place the bytes"

Confirmed by the sigil lane in their own source, and it shrinks step 2's remainder materially.
`SizeSource::Frozen` is live and every shipped profile uses it, **but what it freezes is ORDER
and the ORG-ISLAND ANCHORS — not all placement.** Non-island section bases are *"PACKED from
live-measured sizes … so a size-changing `.emp` parcel shifts downstream sections automatically
instead of colliding with stale pins."* **Everything that is not an island already floats.**

So the thing to bring home is **anchors and order**, not placement wholesale.

**And one contradiction inside that, unresolved, which step 2 trips over before sigil does.**
Their variant doc says ORDER comes from the frozen table. But `packed_true_bases` takes
`map_order` and `anchor_addrs` as *separate* inputs, and `map_order` is read from `map.toml` —
with live comments describing sections *"placed between load_art and bg per map.toml `order`"*.
**So either that doc comment is stale and order has ALREADY come home while anchors have not, or
there are two order authorities and one silently wins.** Sigil is settling it and has explicitly
declined to assert which. **It changes step 2's size**: if order is already home, the remainder
is *anchors + the gate*, not *order + anchors + the gate*.

*(Worth noting how this surfaced: sigil's own status memory said "frozen table retired" — a
different, narrower table — and they nearly planned from it. Third time in one day that a lane's
claim about its own tree needed checking, which is the direction that gets asserted as context
rather than verified as a claim.)*

**Consequence for sequencing, and it is the reason this was worth checking:** sigil's eight
undeclared constraints are **step 2's remaining input, not step 1's**. The ruling says so
explicitly — *every constraint the frozen tables encode today must be recaptured as an explicit
rule BEFORE the tables stop being authority, or it silently stops being enforced*. If step 1
vendors a pinned corpus while the frozen tables are still authority, **the tables get pinned
too, and the constraints they enforce-without-declaring become invisible AND frozen.**

## §1 — Steps 1 and 3 are separable, and the order is 1-then-3

This lane initially priced step 3 as *removing the thing that catches harness reds*, on the
evidence that every red across two chains was harness-side. **The sigil lane corrected that with
a count, and the correction holds**: of the four instances, `Ground_Move_Cap` was caught by
`native_full_rom` (a byte gate), the narrowed `include_root` and the cross-seam reference by
**port gates**, and only the repin baseline is repin-adjacent. **Three of four are caught by
gates step 3 does not touch** — they keep running, against a pinned corpus instead of a live tree.

The order is not a judgement call, because the windows are asymmetric:

- **1 then 3**: `pins.rs` only moves when the snapshot is **bumped**, so `repin`'s landing-path
  role collapses to "runs at snapshot bumps" — which **is** the internal-regression-tool role
  step 3 aims at. Step 3 becomes largely a booking of what step 1 already achieved.
- **3 then 1**: `repin` leaves the landing path while the corpus is still live aeon, so pins
  drift on every aeon commit with nothing regenerating them — **port gates go red on ordinary
  commits, for reasons belonging to neither lane's parcel**, and that window stays open for as
  long as step 1 takes.

## §2 — What aeon owes

1. **The aeon-committed expected CRCs** step 1's nightly job reads. Not merely a file: which
   shapes, at what cadence, and **what a mismatch means when the assembler has legitimately
   moved**. Tonight a relink was byte-neutral **by measurement**, and three lanes checked it
   independently to establish that. **The job's output must discriminate *aeon changed* /
   *sigil changed* / *both* — baked into the output, not left to the reader.**
2. **The aeon-side gate** asserting anchors and room guarantees — step 2's missing third, including
   making `bganim_room` actually run. A room guarantee announced as unchecked is the vacuous-gate
   shape this repo has removed four instances of in one night.
3. **Cutting this lane's `OVERSEER.md` landing-lane section.** ~1,300 lines, a large fraction
   describing the paired-freeze ritual. **A stale procedure is worse than an absent one, because
   it executes.** Sigil has the identical exposure in their landing-lane section, the paired-freeze
   division and the repin ripple. **Agreed: neither lane lands step 3 until BOTH docs are cut**, or
   the first session to boot afterwards runs a ritual for a machine that is gone.

## §3 — The question step 4 must answer, and why it must WAIT

The certification's value was never the goldens; it was that **two independent instruments had to
agree before bytes shipped**. Across two chains it caught **nothing in the engine and four things
in the harness**. That reads as *the gate is spent*. It reads equally as *the gate is why the
engine is clean*. **Neither lane can distinguish those from inside, and step 4 must not be written
from either lane's intuition.**

**Step 1 hands us the instrument** (sigil's, and it is the best idea in the plan): a nightly
non-blocking drift job **still measures byte-identity — it just stops blocking.** So run it
non-blocking for N chains and read the result.

- Engine stays byte-clean while nothing blocks on it → **the gate was spent**, and step 4 says so
  with evidence.
- Reds appear that a landing would have caught → **the gate was load-bearing**, the archive says
  *that*, and the nightly job earns a promotion rather than a retirement.

**So step 4 is gated on data from step 1, not on a decision.** N is unset deliberately; the owner
sets it, and it is the one number in this plan neither lane should choose.

## Constraints in force while this is executed

- **No bytes move and nothing freezes while the owner is authoring in the live aeon tree.**
  `TEST-OBJECTS-DELETE` is parked for the same reason.
- The owner's edits are confined to `data/editor/**` and the regenerated tree; **none touch
  `map.toml`, placement or anchors**, so step 2's remainder is orthogonal to his authoring.
- **Two grants of different scope and lifetime, and neither inherits the other's expiry**
  (sigil's formulation, worth stating because it is easy to blur): the *overnight autonomy*
  directive was given at "I am about to go to bed" and **both lanes read it as LAPSED** now that
  he is awake and directing lanes himself. Sigil's *standing* autonomy on assembler internals
  (re-confirmed 2026-08-24, with an obligation to log notable calls) is a different grant and did
  **not** expire with it. Planning proceeds on his standing yes for the project; **anything that
  moves bytes or changes this plan's shape goes to him, now that he is here to ask.**
