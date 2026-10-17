/**
 * [r215d] F-278's leg on the seeded face vector (ruling 215 record 6200719567;
 * ruling 226 item 2 assigns it to docs with UR-52 waived, beside #7181).
 * Route: /face-recognition. Package text, verbatim: "F-278's leg runs in
 * `Feature check (seeded)`: it opens the seeded person, sees the enrolled
 * face, and deletes it (`DELETE /api/known-persons/{person_id}/embeddings/
 * {embedding_id}`)."
 *
 * WHY THIS FILE IS `.seeded` (the frame that makes it runnable at all):
 *  - frontend/playwright.config.ts splits the golden tree ON FILENAME, read at
 *    this head rather than recalled: project `golden` (name at :283) sets
 *    `testIgnore: /.*\.seeded\.spec\.ts$/` (:285) and project `golden-seeded`
 *    (name at :300) sets `testMatch: /.*\.seeded\.spec\.ts$/` (:302); both
 *    `fullyParallel: false, workers: 1`. CI runs them as two jobs against two
 *    FRESH stacks — `Feature check (fake AI)` runs `--project=golden`,
 *    `Feature check (seeded)` runs `--project=golden-seeded` (feature_check.py
 *    picks `project_name = "golden-seeded" if self.seeded else "golden"`;
 *    quoted, not cited by line number, so a roll above it cannot orphan this
 *    pointer). So this file runs ONLY in the seeded job and persons.spec.ts
 *    (F-275/F-277, not `.seeded`) runs ONLY in the fake-AI job — no shared
 *    stack, and no cross-project interference to reason about.
 *  - The fixture this leg consumes is the harness's own insert (the [r215a]
 *    deliverable, #7188): a `docker compose exec -T backend python -c` that
 *    adds exactly ONE `KnownPerson(name='Seeded Known Person', …, notes='Seeded
 *    by feature_check.py for F-278')` and exactly ONE `FaceEmbedding` (fixed
 *    unit vector, `model_id='test-only-seeded-vector'`, `quality_score=0.95`),
 *    then fails the BOOT unless GET /api/known-persons shows ≥1 item with
 *    `embedding_count >= 1`. A ready seeded stack therefore guarantees what
 *    leg 1 below reads, and the notes string names F-278: the seed exists for
 *    THIS box.
 *  - The stack has NO other sanctioned way to hold a face vector, which is why
 *    UR-153 kept F-278 unverified until [r215a]. `POST /known-persons/{person_id}
 *    /embeddings` is retired-always-410 (its decorator carries `deprecated=True`
 *    plus a 410 responses entry) and `/face-events/match` likewise, so a
 *    client-computed vector is refused BY CONTRACT, not by a test limitation;
 *    the only live creator is `POST /known-persons/bulk-enroll`, whose every
 *    image runs `extract_face_embedding_from_image`, which returns "Face
 *    extractor unavailable: pinned face weights not loaded" without the pinned
 *    SCRFD + w600k_r50 weights. That sentence is why [r215a] had to insert by
 *    ORM instead of calling any route — and why this leg must CONSUME the seed
 *    rather than make its own.
 *
 * THE RETRY LAW — why `test.describe.configure({ retries: 0 })` sits below:
 *  - The golden projects do NOT set `retries`, so they inherit the root
 *    `retries: process.env.CI ? 2 : 0` (playwright.config.ts:80; harness.ts
 *    documents the same inheritance for `golden` and its consequence — junit
 *    merges a retry-absorbed failure into `passed` and golden() reads ONLY
 *    junit, so a green Feature-check row can mean "passed on retry").
 *  - A retry starts a new worker against the SAME live stack: nothing re-seeds
 *    per attempt (the insert is one boot-time call) and teardown is the
 *    boot-time `compose down -v`, after the run. This leg DESTROYS its fixture
 *    — the pool is exactly one embedding and no restore is sanctioned (the two
 *    410s and the extractor-gated bulk-enroll above). So attempt 2 could only
 *    enter a stack whose embedding attempt 1 already deleted, its red would be
 *    a CONSEQUENCE of the real one, and junit would tally the pair `passed`.
 *  - retries: 0 makes attempt 1 final, so the first red ships with its real
 *    message instead of a derived "0 embeddings". The mechanism is repo-native
 *    (`test.describe.configure({ retries: … })` in
 *    tests/e2e/specs/retry-isolation.spec.ts — 2 at :29 and :115, 3 at :276, 1
 *    at :304) but never 0 there, for the opposite reason: those rigs WANT a
 *    re-run to prove isolation from a recoverable flake. Here the fixture is
 *    consumable-once, so a second attempt can only lie.
 *
 * WHAT THE LEG PROVES, IN ORDER (backend fact first, then the UI that renders
 * it — persons.spec.ts's doctrine; the DELETE is the box's named contract and
 * is deliberately the LAST action that changes state):
 *  1. GET /api/known-persons carries EXACTLY ONE item with
 *     `embedding_count >= 1` and it is named 'Seeded Known Person'. Exactly-one
 *     is the plan's own claim, not paranoia: [r215a]'s package text says
 *     "inserts one known person and one face-embedding row", so a second
 *     seeded person means the plan changed and this leg should notice by NAME
 *     instead of following whichever item sorts first.
 *  2. GET /api/known-persons/{person_id} (the route the row lists FIRST) answers
 *     200 for that id with the seed's OWN `notes` string and
 *     `embedding_count == 1`. Both halves matter: `notes` proves the profile
 *     route round-trips the SEEDED row rather than merely some row, and the
 *     count is computed independently (`len(person.embeddings)` at
 *     face_recognition.py:203), so it corroborates the embedding leg instead of
 *     repeating it. The row's action clause is three-part — "sees the profile
 *     AND enrolled face embeddings; deletes one" — which is why a flip that
 *     covered embeddings+delete alone would be short.
 *  3. GET /api/known-persons/{id}/embeddings answers 200 with a BARE array of
 *     exactly one row carrying a numeric `id` and `quality_score` (the route
 *     the inventory row lists; `list_person_embeddings` declares
 *     `response_model=list[FaceEmbeddingResponse]`, and unlike the persons
 *     LIST it is not enveloped — see HISTORY below for why that distinction is
 *     load-bearing HERE and not merely stylistic).
 *  4. The card PAINTS and the click opens the detail modal titled with the
 *     person's own name (`Dialog.Title as="h2"`) — the card leg exists only
 *     because the row's action clause starts "clicks a person card".
 *  5. The modal renders the seed's `notes` in its profile block, so
 *     `get_known_person` is proved through the shipped UI and not only through
 *     my own fetch. The household and trust fields are deliberately NOT
 *     asserted — the seed sets `is_household_member=True` with no member id, so
 *     both fall through to fixture defaults ("Yes"/"Monitor") and pinning them
 *     would bless an artifact of the fixture (comment at that leg).
 *  6. "sees the enrolled face": heading `Face Embeddings (1)` EXACT, the card
 *     for THIS embedding id, its quality badge equal to the API's own
 *     `quality_score.toFixed(2)` (0.95 → "0.95", so the badge is bound to the
 *     API echo rather than to a literal), and the empty copy ABSENT. The
 *     heading is the state witness, not a label: it renders only after
 *     `isLoading` clears (KnownPersonDetailModal.tsx:285-298), so it also
 *     proves the embeddings fetch settled. NOTE the deliberate omission here —
 *     `data-testid="face-embeddings-gallery"` (:308) wraps the empty AND the
 *     filled branch, so asserting it visible cannot distinguish "1 embedding"
 *     from "0"; it is asserted as the container mount only, never as proof of
 *     an enrolled face.
 *  7. The DELETE the box names, driven through the shipped confirm flow
 *     (hover-independent: `aria-label="Delete embedding"` → the `Confirm
 *     Delete` dialog and its warning copy → `Confirm`; skipping the dialog
 *     would not be driving the app). A response counter pinned to the EXACT
 *     pathname must read exactly ONE DELETE and carry 204, the route's own
 *     `status_code=204` — so the leg proves the UI fired F-278's contract, not
 *     merely that pixels moved.
 *  8. Proof through the routes the page itself refetches: GET embeddings → 200
 *     and `[]` (the row is gone server-side), then the UI's OWN refetch —
 *     `useDeleteEmbedding` invalidates the personEmbeddings key on success, so
 *     no reload trick is involved: heading `Face Embeddings (0)`, the card
 *     gone, and the shipped empty copy VERBATIM ("No face embeddings yet. Add
 *     one from a detection event." — persons.spec.ts:242-248's lesson, that
 *     matching only a first sentence let copy which had lost its second half
 *     pass).
 *  9. `assertGuardSurvives` last, as every golden identity leg ends.
 *
 * ON `test.setTimeout(90_000)`: zones.spec.ts:593-609 argues the OPPOSITE and
 * its reasoning is good — a timeout abandons `finally` un-run, which leaked a
 * household member at 3377684a6 and reddened both retries on their own
 * fresh-state gate. That argument does not bind here, for two measured reasons:
 * this leg HAS no `finally` (its fixture is destroyed by design and the stack
 * is torn down after the run, so there is no restore a timeout could skip), and
 * the config's default test budget is 15 s (`playwright.config.ts:113`), which
 * cannot be paired with the 15 s `poll` the DELETE leg needs — the poll's own
 * message could never print, because the test would time out first. Both
 * sibling `.seeded` specs make the same choice for the same class of reason
 * (operations/recording-replay.seeded.spec.ts:38 and
 * operations/debug-mode-toggle.seeded.spec.ts:22, each 90_000 with a 15 s
 * poll). No wall-clock claim is made: the local seeded boot cannot run in THIS
 * sandbox (harness aborts on `open_count: 0` from stale local images while CI's
 * seeded job is green on main), so CI is the venue that measures this leg, and
 * if 90 s ever looks wrong the evidence to post is golden-playwright.log's
 * duration, per zones.spec.ts's rule.
 *
 * DELIBERATE NON-CLAIMS:
 *  - No toast assertion. The success copy is sonner-rendered; the delete's
 *     proof rides on the route counter, its 204, the GET and the gallery.
 *  - It does not re-prove F-275's card contract (persons.spec.ts owns the
 *     empty mount, the count badge and the write routes); the card leg here
 *     exists because the box says "opens the seeded person".
 *  - Nothing about re-identification: the vector is test-only
 *     (`model_id='test-only-seeded-vector'`); matching, face-events and the
 *     enrollment queue are F-276/F-279/F-280.
 *  - HISTORY, kept because it is load-bearing: persons.spec.ts's header still
 *     narrates the known-persons CARD as MEASURED RED (Break A: the hook passed
 *     the `KnownPersonListResponse` envelope through, so `?.length ?? 0` read
 *     empty and the card never painted). a51a3aad9 ("fix(FE-2): unwrap the
 *     known-persons list envelope", 2026-10-11, an ancestor of this head) fixed
 *     that, and the F-275 gallery leg now PASSES FIRST-ATTEMPT on main (run
 *     38837481347 results map `passed`, with 0 `flaky` / 0 `(retry #)` / 0 `✘`
 *     in its list stdout). Two consequences, both respected here: this leg may
 *     write its card asserts against FIXED behaviour, and the embeddings route
 *     must NOT be assumed enveloped the way the list once was — it returns a
 *     bare array, which leg 3 asserts rather than trusts. Nor is that header
 *     edited here: F-275's inventory row pins THIS FILE'S SIBLING as its
 *     witness — "spec blob `48e1758c1` identical at witness and head" — so a
 *     comment-only edit to persons.spec.ts would silently break the hash that
 *     row cites, which is a witness question for that row's owner to settle,
 *     not a typo to fix under cover of a different package. It is raised on
 *     #6996 (that PR's own thread) instead.
 */
import { expect, test } from '../guard';
import {
  adminSessionId as adminSession,
  apiPath,
  assertGuardSurvives,
  authedFetch,
  login,
  readHarness,
  type Harness,
} from '../harness';

const harness = readHarness();
test.skip(
  !harness.ready,
  `golden path needs the feature-check stack (${harness.ready ? '' : harness.why})`
);

// The seed is a consumable pool-1 fixture with no sanctioned restore, so a
// second attempt could only run against the world the first attempt destroyed.
// Full reasoning in the header's THE RETRY LAW section.
test.describe.configure({ retries: 0 });

/** The seed's name, quoted from the insert this stack's boot performs
 *  (feature_check.py, [r215a]/#7188). If the seed's name changes this leg
 *  fails BY NAME — which is the notification [r215d]'s box depends on. */
const SEEDED_PERSON = 'Seeded Known Person';

/** The seed's own notes string (feature_check.py's insert, verbatim). Used as
 *  the PROFILE witness: the modal renders it only when the person carries
 *  notes (KnownPersonDetailModal.tsx:746-751, `{person.notes && …}`), so
 *  seeing it proves `GET /api/known-persons/{person_id}` round-tripped a
 *  seed-SPECIFIC field — a stronger profile proof than the name, which the
 *  card already carried into the page. It doubles as the leg's own signature:
 *  the string names F-278, so a green leg is a green F-278 leg. */
const SEED_NOTES = 'Seeded by feature_check.py for F-278';

/** Verbatim from the shipped empty branch (KnownPersonDetailModal.tsx:311).
 *  ONE constant for both the "absent while enrolled" and "present after the
 *  delete" halves, so the pair cannot drift apart. */
const EMPTY_COPY = 'No face embeddings yet. Add one from a detection event.';

interface KnownPersonItem {
  id: number;
  name: string;
  embedding_count?: number;
}

interface FaceEmbeddingRow {
  id: number;
  person_id: number;
  quality_score: number;
}

test.describe('seeded golden path: delete the seeded face embedding (F-278)', () => {
  test.setTimeout(90_000);

  test('opens the seeded person, sees the enrolled face, and deletes it', async ({ page }) => {
    // ONE session for both legs (household.spec.ts's signIn shape): adminSession
    // is a real POST /api/auth/login, and calling it twice would mint a second
    // cookie the spec never needed.
    const h = harness as Harness;
    const session = await adminSession(h);
    const api = await authedFetch(h, session);
    await login(page, h, session);

    // --- 1. backend fact: the seed is there, exactly once, and it is ours. ---
    const people = await api.getJson('/api/known-persons');
    expect(people.status, 'GET /api/known-persons answers 200').toBe(200);
    const seeded = ((people.body?.items ?? []) as KnownPersonItem[]).filter(
      (item) => (item.embedding_count ?? 0) >= 1
    );
    expect(
      seeded,
      `the seeded stack holds exactly one person with an embedding, got ${JSON.stringify(
        people.body?.items
      )}`
    ).toHaveLength(1);
    const person = seeded[0];
    expect(person.name, "the seeded person carries [r215a]'s name").toBe(SEEDED_PERSON);

    // --- 2. backend fact: the ROW'S SECOND LISTED ROUTE answers, and it is
    //     the same row. F-278's action clause is three-part — "sees the profile
    //     AND enrolled face embeddings; deletes one" — and its route list names
    //     GET /api/known-persons/{person_id} first, so a flip that covered only
    //     embeddings+delete would leave that clause unproved. The notes field is
    //     the witness: KnownPersonResponse declares it (backend/api/schemas/
    //     face_recognition.py:102) and the seed is what set it, so this proves
    //     the profile route round-trips the SEEDDED row rather than any row.
    const profile = await api.getJson(`/api/known-persons/${person.id}`);
    expect(
      profile.status,
      'GET /api/known-persons/{person_id} answers 200 for the seeded row'
    ).toBe(200);
    expect(profile.body?.name, 'the profile route is the same person').toBe(SEEDED_PERSON);
    expect(
      profile.body?.notes,
      "the profile route carries the seed's own notes (round-trip proof)"
    ).toBe(SEED_NOTES);
    // The profile route computes its own count (`len(person.embeddings)`,
    // face_recognition.py:203) rather than echoing the list, so this is a second
    // independent witness that exactly one embedding exists — not a repeat.
    expect(profile.body?.embedding_count, 'the profile route counts the seeded embedding').toBe(1);

    // --- 3. backend fact: the embedding route answers with one real row. ---
    const embeddingsPath = `/api/known-persons/${person.id}/embeddings`;
    const embeddings = await api.getJson(embeddingsPath);
    expect(embeddings.status, 'GET …/{id}/embeddings answers 200').toBe(200);
    expect(
      Array.isArray(embeddings.body),
      `the embeddings route answers a BARE array, got ${JSON.stringify(embeddings.body)}`
    ).toBe(true);
    const rows = (embeddings.body ?? []) as FaceEmbeddingRow[];
    expect(rows, 'the seed inserts exactly one embedding ([r215a])').toHaveLength(1);
    const embedding = rows[0];
    expect(typeof embedding.id, 'the embedding row carries a numeric id').toBe('number');
    // Bound the UI badge to the API echo (0.95 -> "0.95"), never to a literal.
    const qualityText = embedding.quality_score.toFixed(2);

    // --- pin the box's route BEFORE any click can fire it. ---
    // apiPath() (harness.ts:209) is the identity tree's matcher — exact-path
    // equality with one optional trailing slash removed, never endsWith(), so
    // this predicate can neither bind a sibling route nor silently never fire
    // and skip the code it guards.
    const deletePath = `/api/known-persons/${person.id}/embeddings/${embedding.id}`;
    let deleteCalls = 0;
    let deleteStatus = 0;
    page.on('response', (res) => {
      try {
        if (apiPath(res.url()) === deletePath && res.request().method() === 'DELETE') {
          deleteCalls += 1;
          deleteStatus = res.status();
        }
      } catch {
        /* non-http responses (recording-replay.seeded.spec.ts precedent) */
      }
    });

    // --- 4. the card paints and the modal opens on the seeded person. ---
    await page.goto(`${h.ui}/face-recognition`, { waitUntil: 'domcontentloaded' });
    // exact: true is load-bearing, not tidiness: getByRole's accessible-name
    // match is a case-insensitive SUBSTRING, and harness.ts:243-264 documents a
    // real strict-mode red from exactly that (a vehicle whose title prefixes a
    // member's matched two cards). Nothing today names a second person
    // "Seeded Known Person …", and that is precisely the kind of fact a later
    // fixture silently invalidates.
    const card = page.getByRole('button', {
      name: `View details for ${SEEDED_PERSON}`,
      exact: true,
    });
    await expect(card, 'the seeded person paints a card (Break A is fixed)').toBeVisible();
    await card.click();
    await expect(
      page.getByRole('heading', { name: SEEDED_PERSON, level: 2, exact: true }),
      'the detail modal titles itself with the person name (get_known_person)'
    ).toBeVisible();

    // --- 5. "sees the profile" — the modal's own render of get_known_person.
    //     Scoped to the label pair rather than a page-wide text match: `Notes:`
    //     is a one-off label today, but a scoped locator is the same defense
    //     harness.ts:243-264 argues for on the cards.
    //     Deliberately NOT asserted: `Linked Household` and `Trust Level`. The
    //     seed sets is_household_member=True with NO household_member_id
    //     (feature_check.py's insert), so both fields resolve through their
    //     fallbacks — `undefined?.name ?? 'Yes'` and the final 'Monitor' branch.
    //     Pinning either would bless a fixture artifact as a contract, and the
    //     day [r215a] gives the seed a real member id they would both change
    //     with no defect anywhere.
    // Two asserts, not a parent-scoped pair: Playwright's text engine matches
    // the DEEPEST element holding the text, so `Notes:` (its own span) and the
    // value (its own span) are each one node — a locator built on the parent
    // div would have to reason about ancestor matches for no extra truth.
    await expect(page.getByText('Notes:', { exact: true })).toBeVisible();
    await expect(
      page.getByText(SEED_NOTES, { exact: true }),
      "the modal renders the seeded person's own notes field"
    ).toBeVisible();

    // --- 6. "sees the enrolled face". ---
    // The heading is the state witness: it renders only after isLoading
    // clears, so it also proves the embeddings fetch settled.
    await expect(
      page.getByRole('heading', { name: 'Face Embeddings (1)', level: 3, exact: true })
    ).toBeVisible();
    // Container mount ONLY — this testid wraps the empty and the filled branch
    // (:308), so it can never witness an enrolled face. The two asserts below
    // carry that weight.
    await expect(page.getByTestId('face-embeddings-gallery')).toBeVisible();
    const embeddingCard = page.getByTestId(`embedding-card-${embedding.id}`);
    await expect(
      embeddingCard,
      'the gallery renders the card for the SEEDED embedding id, not merely a card'
    ).toBeVisible();
    await expect(embeddingCard.getByText(qualityText, { exact: true })).toBeVisible();
    // The empty branch must be OFF while the gallery is filled — otherwise a
    // page rendering BOTH states would satisfy everything above.
    await expect(page.getByText(EMPTY_COPY)).toHaveCount(0);

    // --- 7. the box's DELETE, through the shipped confirm flow. ---
    await embeddingCard.getByRole('button', { name: 'Delete embedding' }).click();
    await expect(
      page.getByText('Are you sure you want to delete this face embedding?')
    ).toBeVisible();
    await page.getByRole('button', { name: 'Confirm', exact: true }).click();
    await expect
      .poll(() => deleteCalls, {
        timeout: 15_000,
        intervals: [250],
        message: `expected exactly one DELETE ${deletePath}`,
      })
      .toBe(1);
    expect(deleteStatus, 'the delete route answers its declared 204').toBe(204);

    // --- 8. proof through the refetched route, then the refetched UI. ---
    const after = await api.getJson(embeddingsPath);
    expect(after.status, 'the embeddings route still answers after the delete').toBe(200);
    expect(
      (after.body ?? []) as FaceEmbeddingRow[],
      'the seeded embedding row is gone server-side'
    ).toHaveLength(0);
    await expect(
      page.getByRole('heading', { name: 'Face Embeddings (0)', level: 3, exact: true })
    ).toBeVisible();
    await expect(page.getByTestId(`embedding-card-${embedding.id}`)).toHaveCount(0);
    await expect(page.getByText(EMPTY_COPY)).toBeVisible();

    // --- 9. the page/context guard survived a mutation drive. ---
    await assertGuardSurvives(page, h);
  });
});
