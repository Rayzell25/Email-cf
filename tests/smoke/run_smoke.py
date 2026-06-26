"""End-to-end smoke test for the bot's handler + service logic.

Runs WITHOUT the real third-party libraries (they are stubbed -- see stubs.py)
and WITHOUT a real Telegram/Cloudflare connection (fakes below). It drives the
actual handler and service code paths and asserts the dashboard transitions and
the resulting fake-Cloudflare state, so genuine logic/flow/attribute bugs are
caught.

Run:  python -m tests.smoke.run_smoke
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone
from types import SimpleNamespace

# --- env + stubs MUST be set before importing app ---------------------------
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456:TEST")
os.environ.setdefault("TELEGRAM_OWNER_ID", "42")
os.environ.setdefault("CLOUDFLARE_API_TOKEN", "cf-test-token")
os.environ.setdefault("CLOUDFLARE_ACCOUNT_ID", "acc123")
os.environ.setdefault("DEFAULT_DESTINATION_EMAIL", "inbox@dest.com")
os.environ.setdefault("USE_PREMIUM_EMOJI", "0")

# ensure repo root on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from tests.smoke import stubs  # noqa: E402

stubs.install()

# now the real app modules can import
from app.database import models as M  # noqa: E402
from app.database.repositories import (  # noqa: E402
    audit as audit_repo,
    batches as batches_repo,
    dashboard as dashboard_repo,
    emails as emails_repo,
    names as names_repo,
    users as users_repo,
)
from app.services import cloudflare as cf_mod  # noqa: E402
from app.handlers import (  # noqa: E402
    create_manual,
    create_random,
    domains,
    email_delete,
    email_list,
    menu,
    start,
)
from app.handlers import states  # noqa: E402
from app.middlewares.owner_only import OwnerOnlyMiddleware  # noqa: E402

OWNER_ID = 42


# ===========================================================================
# In-memory database backing the repository functions
# ===========================================================================
class Store:
    def __init__(self):
        self.names: dict[str, SimpleNamespace] = {}
        self.emails: dict[str, SimpleNamespace] = {}
        self.batches: dict[int, SimpleNamespace] = {}
        self.items: dict[int, list] = {}
        self.dashboards: dict[int, SimpleNamespace] = {}
        self.audits: list = []
        self._nid = 0
        self._eid = 0
        self._bid = 0
        self._iid = 0

    def next_name_id(self):
        self._nid += 1
        return self._nid

    def next_batch_id(self):
        self._bid += 1
        return self._bid

    def next_item_id(self):
        self._iid += 1
        return self._iid


DB = Store()


def _aware(dt):
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ---- patch users ----
async def _users_get_or_create(session, uid):
    return SimpleNamespace(id=uid, telegram_user_id=uid, is_allowed=True)


users_repo.get_or_create = _users_get_or_create


# ---- patch dashboard ----
async def _dash_get(session, uid):
    return DB.dashboards.get(uid)


async def _dash_upsert(session, telegram_user_id, chat_id, message_id):
    rec = SimpleNamespace(
        telegram_user_id=telegram_user_id, chat_id=chat_id, message_id=message_id
    )
    DB.dashboards[telegram_user_id] = rec
    return rec


dashboard_repo.get = _dash_get
dashboard_repo.upsert = _dash_upsert


# ---- patch names ----
async def _names_get(session, normalized):
    return DB.names.get(normalized)


async def _names_is_taken(session, normalized, now=None):
    now = now or datetime.now(timezone.utc)
    row = DB.names.get(normalized)
    if row is None:
        return False
    if row.status in (M.NameStatus.created.value, M.NameStatus.deleted.value,
                      M.NameStatus.failed.value):
        return True
    if row.status == M.NameStatus.reserved.value:
        if row.reserved_until is not None and _aware(row.reserved_until) <= now:
            return False
        return True
    return False


async def _names_reserve(session, display_name, normalized, token, reserved_until):
    existing = DB.names.get(normalized)
    if existing is not None:
        if await _names_is_taken(session, normalized):
            return None
        existing.display_name = display_name
        existing.status = M.NameStatus.reserved.value
        existing.reservation_token = token
        existing.reserved_until = reserved_until
        existing.deleted_at = None
        return existing
    row = SimpleNamespace(
        id=DB.next_name_id(),
        display_name=display_name,
        normalized_name=normalized,
        status=M.NameStatus.reserved.value,
        reservation_token=token,
        reserved_until=reserved_until,
        deleted_at=None,
        created_at=datetime.now(timezone.utc),
    )
    DB.names[normalized] = row
    return row


async def _names_release(session, token):
    n = 0
    for row in DB.names.values():
        if row.reservation_token == token and row.status == M.NameStatus.reserved.value:
            row.status = M.NameStatus.expired.value
            row.reservation_token = None
            n += 1
    return n


async def _names_set_status(session, normalized, status):
    row = DB.names.get(normalized)
    if row is None:
        return
    row.status = status.value
    if status == M.NameStatus.deleted:
        row.deleted_at = datetime.now(timezone.utc)
    if status in (M.NameStatus.created, M.NameStatus.failed):
        row.reservation_token = None


names_repo.get_by_normalized = _names_get
names_repo.is_taken = _names_is_taken
names_repo.reserve = _names_reserve
names_repo.release_by_token = _names_release
names_repo.set_status = _names_set_status


# ---- patch emails ----
async def _emails_get(session, full_email):
    return DB.emails.get(full_email.lower())


async def _emails_exists_active(session, full_email):
    row = DB.emails.get(full_email.lower())
    return row is not None and row.status == M.EmailStatus.active.value


async def _emails_record_created(session, *, zone_id, domain, local_part,
                                 normalized_local_part, full_email, rule_id,
                                 destination_email, source):
    full = full_email.lower()
    row = DB.emails.get(full) or SimpleNamespace(created_at=datetime.now(timezone.utc))
    row.zone_id = zone_id
    row.domain = domain
    row.local_part = local_part
    row.normalized_local_part = normalized_local_part
    row.full_email = full
    row.cloudflare_rule_id = rule_id
    row.destination_email = destination_email
    row.source = source.value
    row.status = M.EmailStatus.active.value
    row.deleted_at = None
    DB.emails[full] = row
    return row


async def _emails_record_deleted(session, full_email):
    row = DB.emails.get(full_email.lower())
    if row is not None:
        row.status = M.EmailStatus.deleted.value
        row.deleted_at = datetime.now(timezone.utc)


async def _emails_get_for_rule(session, zone_id, rule_id):
    for row in DB.emails.values():
        if row.zone_id == zone_id and getattr(row, "cloudflare_rule_id", None) == rule_id:
            return row
    return None


async def _emails_count_active(session):
    return sum(1 for r in DB.emails.values() if r.status == M.EmailStatus.active.value)


async def _emails_get_active_for_zone(session, zone_id):
    return [r for r in DB.emails.values()
            if r.zone_id == zone_id and r.status == M.EmailStatus.active.value]


emails_repo.get_by_full_email = _emails_get
emails_repo.exists_active = _emails_exists_active
emails_repo.record_created = _emails_record_created
emails_repo.record_deleted = _emails_record_deleted
emails_repo.get_for_rule = _emails_get_for_rule
emails_repo.count_active = _emails_count_active
emails_repo.get_active_for_zone = _emails_get_active_for_zone


# ---- patch batches ----
async def _batch_create(session, *, telegram_user_id, zone_id, domain,
                        requested_count, status=M.BatchStatus.draft):
    b = SimpleNamespace(
        id=DB.next_batch_id(),
        telegram_user_id=telegram_user_id,
        zone_id=zone_id,
        domain=domain,
        requested_count=requested_count,
        status=status.value,
        items=[],
        completed_at=None,
    )
    DB.batches[b.id] = b
    DB.items[b.id] = []
    return b


async def _batch_get(session, batch_id):
    return DB.batches.get(batch_id)


async def _batch_set_status(session, batch, status):
    batch.status = status.value
    if status in (M.BatchStatus.completed, M.BatchStatus.partial, M.BatchStatus.failed,
                  M.BatchStatus.cancelled, M.BatchStatus.expired):
        batch.completed_at = datetime.now(timezone.utc)


async def _batch_try_lock(session, batch_id):
    b = DB.batches.get(batch_id)
    if b is None:
        return None
    if b.status in (M.BatchStatus.processing.value, M.BatchStatus.completed.value,
                    M.BatchStatus.cancelled.value, M.BatchStatus.expired.value):
        return None
    b.status = M.BatchStatus.processing.value
    return b


async def _batch_replace_items(session, batch, emails):
    items = []
    for email in emails:
        items.append(SimpleNamespace(
            id=DB.next_item_id(),
            batch_id=batch.id,
            full_email=email,
            status=M.BatchItemStatus.pending.value,
            error_message=None,
            cloudflare_rule_id=None,
            generated_name_id=None,
        ))
    DB.items[batch.id] = items
    batch.items = items
    return items


async def _batch_get_items(session, batch_id):
    return list(DB.items.get(batch_id, []))


batches_repo.create_batch = _batch_create
batches_repo.get_batch = _batch_get
batches_repo.set_batch_status = _batch_set_status
batches_repo.try_lock_for_processing = _batch_try_lock
batches_repo.replace_items = _batch_replace_items
batches_repo.get_items = _batch_get_items


# ---- patch audit ----
async def _audit_log(session, *, telegram_user_id, action, target=None,
                     status=None, details=None):
    DB.audits.append((action, target, status))


audit_repo.log = _audit_log


# ===========================================================================
# Fake Cloudflare client
# ===========================================================================
class FakeCloudflare:
    def __init__(self):
        self.zones = [
            cf_mod.Zone("z_example", "example.com", "active"),
            cf_mod.Zone("z_test", "test.org", "active"),
        ]
        self.rules: dict[str, dict[str, cf_mod.RoutingRule]] = {
            "z_example": {}, "z_test": {}
        }
        self.fail_count = 0  # number of next create calls that should fail
        self.create_calls = 0
        self._rid = 0

    async def list_zones(self):
        return sorted(self.zones, key=lambda z: z.name.lower())

    async def get_email_routing_status(self, zone_id):
        return {"enabled": True, "status": "ready"}

    async def list_routing_rules(self, zone_id):
        return sorted(self.rules.get(zone_id, {}).values(), key=lambda r: r.email)

    async def find_rule_by_email(self, zone_id, email):
        return self.rules.get(zone_id, {}).get(email.lower())

    async def create_routing_rule(self, zone_id, email, destination):
        self.create_calls += 1
        if self.fail_count > 0:
            self.fail_count -= 1
            raise cf_mod.CloudflareError("Simulasi gagal create dari Cloudflare.")
        self._rid += 1
        rule = cf_mod.RoutingRule(
            id=f"rule_{self._rid}", email=email.lower(),
            destination=destination, enabled=True,
        )
        self.rules.setdefault(zone_id, {})[email.lower()] = rule
        return rule

    async def delete_routing_rule(self, zone_id, rule_id):
        bucket = self.rules.get(zone_id, {})
        for email, rule in list(bucket.items()):
            if rule.id == rule_id:
                del bucket[email]
                return
        raise cf_mod.CloudflareError("rule not found", status=404)

    async def close(self):
        pass

    def total_rules(self, zone_id):
        return len(self.rules.get(zone_id, {}))


# ===========================================================================
# Fake aiogram primitives
# ===========================================================================
from aiogram.types import CallbackQuery, Message  # noqa: E402


class FakeState:
    def __init__(self):
        self._data = {}
        self._state = None

    async def get_data(self):
        return dict(self._data)

    async def update_data(self, **kw):
        self._data.update(kw)
        return dict(self._data)

    async def set_data(self, data):
        self._data = dict(data)

    async def set_state(self, state):
        self._state = state

    async def get_state(self):
        return self._state

    async def clear(self):
        self._data = {}
        self._state = None


class FakeBot:
    def __init__(self):
        self.last_text = None
        self.last_markup = None
        self._mid = 100
        self.deleted = []
        self.session = SimpleNamespace(close=_noop)

    async def send_message(self, chat_id, text, reply_markup=None, **k):
        self.last_text = text
        self.last_markup = reply_markup
        self._mid += 1
        return Message(message_id=self._mid, text=text,
                       chat=SimpleNamespace(id=chat_id), from_user=None)

    async def edit_message_text(self, text, chat_id, message_id, reply_markup=None, **k):
        self.last_text = text
        self.last_markup = reply_markup
        return True

    async def delete_message(self, chat_id, message_id):
        self.deleted.append(message_id)
        return True


async def _noop(*a, **k):
    pass


def make_user(uid=OWNER_ID):
    return SimpleNamespace(id=uid)


def make_message(text="", uid=OWNER_ID, chat_id=OWNER_ID):
    msg = Message(text=text, from_user=make_user(uid),
                  chat=SimpleNamespace(id=chat_id), message_id=1)
    msg._deleted = False

    async def _delete():
        msg._deleted = True

    async def _answer(t=None, **k):
        pass

    msg.delete = _delete
    msg.answer = _answer
    return msg


def make_callback(data, uid=OWNER_ID, chat_id=OWNER_ID):
    inner = make_message(uid=uid, chat_id=chat_id)
    cbq = CallbackQuery(data=data, from_user=make_user(uid), message=inner)
    cbq._acks = []

    async def _answer(t=None, show_alert=False):
        cbq._acks.append((t, show_alert))

    cbq.answer = _answer
    return cbq


# ===========================================================================
# Assertions / harness
# ===========================================================================
class Harness:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.failures: list[str] = []

    def check(self, cond, label):
        if cond:
            self.passed += 1
            print(f"  PASS  {label}")
        else:
            self.failed += 1
            self.failures.append(label)
            print(f"  FAIL  {label}")

    def section(self, title):
        print(f"\n=== {title} ===")


def kb_callbacks(markup):
    if markup is None:
        return []
    return [b.callback_data for row in markup.inline_keyboard for b in row]


def kb_texts(markup):
    if markup is None:
        return []
    return [b.text for row in markup.inline_keyboard for b in row]


# ===========================================================================
# Scenarios
# ===========================================================================
async def run() -> int:
    h = Harness()
    bot = FakeBot()
    cf = FakeCloudflare()
    state = FakeState()
    session = SimpleNamespace(commit=_noop, rollback=_noop, flush=_noop)

    # ---- S1: /start ----
    h.section("S1 /start dashboard")
    msg = make_message(text="/start")
    await start.on_start(msg, bot, session, state, cf)
    h.check("CLOUDFLARE EMAIL MANAGER" in (bot.last_text or ""), "menu text shown")
    h.check("m:create" in kb_callbacks(bot.last_markup), "BUAT EMAIL button present")
    h.check(msg._deleted, "user /start message deleted")
    h.check(OWNER_ID in DB.dashboards, "dashboard record stored")

    # ---- S1b: /start again removes the old dashboard, keeps a single message ----
    h.section("S1b /start again -> old menu removed")
    old_dash_id = DB.dashboards[OWNER_ID].message_id
    await start.on_start(make_message(text="/start"), bot, session, state, cf)
    new_dash_id = DB.dashboards[OWNER_ID].message_id
    h.check(old_dash_id in bot.deleted, "previous dashboard message deleted")
    h.check(new_dash_id != old_dash_id, "a new single dashboard message created")

    # ---- S2: open create -> domain list ----
    h.section("S2 BUAT EMAIL -> domain list")
    await domains.on_menu_entry(make_callback("m:create"), bot, session, state, cf)
    h.check("example.com" in kb_texts(bot.last_markup), "domain example.com listed")
    h.check("d:sel:c:0" in kb_callbacks(bot.last_markup), "domain select callback present")

    # ---- S3: select domain -> method chooser ----
    h.section("S3 pilih domain -> metode")
    await domains.on_domain_select(make_callback("d:sel:c:0"), bot, session, state, cf)
    h.check("CREATE EMAIL" in (bot.last_text or ""), "method screen shown")
    cbs = kb_callbacks(bot.last_markup)
    h.check("c:rand" in cbs and "c:man" in cbs, "random + manual buttons present")
    h.check((await state.get_data()).get("domain") == "example.com", "domain saved in state")

    # ---- S4: random -> count ----
    h.section("S4 random -> pilih jumlah")
    await create_random.on_random(make_callback("c:rand"), bot, session, state)
    h.check("RANDOM" in (bot.last_text or ""), "count screen shown")
    h.check("r:cnt:4" in kb_callbacks(bot.last_markup), "count button 4 present")

    # ---- S5: choose 4 -> confirm ----
    h.section("S5 pilih 4 -> konfirmasi")
    await create_random.on_count(make_callback("r:cnt:4"), bot, session, state, cf)
    text = bot.last_text or ""
    h.check("CONFIRM" in text, "confirm screen shown")
    h.check(text.count("@example.com") == 4, "exactly 4 emails generated")
    batch_id = (await state.get_data()).get("batch_id")
    h.check(batch_id is not None, "batch id stored")
    confirm_emails = [ln for ln in text.splitlines() if "@example.com" in ln]
    norms_before = set(confirm_emails)

    # ---- S6: reroll ----
    h.section("S6 acak ulang")
    await create_random.on_reroll(make_callback(f"r:re:{batch_id}"), bot, session, state, cf)
    text2 = bot.last_text or ""
    h.check(text2.count("@example.com") == 4, "reroll still 4 emails")
    rerolled = [ln for ln in text2.splitlines() if "@example.com" in ln]
    h.check(set(rerolled) != norms_before, "reroll produced different names")

    # ---- S7: confirm -> create all ----
    h.section("S7 buat semua")
    await create_random.on_confirm(make_callback(f"r:ok:{batch_id}"), bot, session, state, cf)
    h.check("EMAILS CREATED" in (bot.last_text or ""), "success screen shown")
    h.check(cf.total_rules("z_example") == 4, "4 rules created on Cloudflare")
    h.check(DB.batches[batch_id].status == M.BatchStatus.completed.value, "batch completed")

    # ---- S8: double-click confirm (must be a no-op) ----
    h.section("S8 anti double-click")
    rules_before = cf.create_calls
    cbq = make_callback(f"r:ok:{batch_id}")
    await create_random.on_confirm(cbq, bot, session, state, cf)
    h.check(cf.create_calls == rules_before, "no extra create on double click")
    h.check(any(a[1] for a in cbq._acks), "user warned via alert")

    # ---- S9: partial failure + retry ----
    h.section("S9 sebagian gagal -> ganti & coba lagi")
    state2 = FakeState()
    await domains.on_menu_entry(make_callback("m:create"), bot, session, state2, cf)
    await domains.on_domain_select(make_callback("d:sel:c:0"), bot, session, state2, cf)
    cf.fail_count = 1  # first create of this batch fails
    await create_random.on_count(make_callback("r:cnt:2"), bot, session, state2, cf)
    bid2 = (await state2.get_data()).get("batch_id")
    await create_random.on_confirm(make_callback(f"r:ok:{bid2}"), bot, session, state2, cf)
    h.check("CREATION FINISHED" in (bot.last_text or ""), "partial result shown")
    h.check(DB.batches[bid2].status == M.BatchStatus.partial.value, "batch marked partial")
    items = DB.items[bid2]
    h.check(sum(1 for it in items if it.status == "failed") == 1, "exactly 1 failed item")
    # retry the failed one (fail_count now 0 -> should succeed)
    await create_random.on_retry_failed(
        make_callback(f"r:rf:{bid2}"), bot, session, state2, cf
    )
    h.check("EMAILS CREATED" in (bot.last_text or ""), "retry succeeded")
    items2 = DB.items[bid2]
    h.check(all(it.status == "created" for it in items2), "all items created after retry")

    # ---- S10: list emails ----
    h.section("S10 list email per domain")
    await domains.on_menu_entry(make_callback("m:list"), bot, session, state, cf)
    await domains.on_domain_select(make_callback("d:sel:l:0"), bot, session, state, cf)
    total = cf.total_rules("z_example")
    h.check(f"Total emails: <b>{total}</b>" in (bot.last_text or ""), "email count shown")
    h.check(any(c and c.startswith("e:v:") for c in kb_callbacks(bot.last_markup)),
            "email view buttons present")

    # ---- S11: view detail ----
    h.section("S11 detail email")
    await email_list.on_view(make_callback("e:v:0"), bot, session, state, cf)
    h.check("EMAIL DETAILS" in (bot.last_text or ""), "detail screen shown")
    h.check("e:del:0" in kb_callbacks(bot.last_markup), "delete button present")

    # ---- S12: delete ----
    h.section("S12 hapus email")
    before = cf.total_rules("z_example")
    await email_delete.on_delete(make_callback("e:del:0"), bot, session, state)
    h.check("DELETE EMAIL" in (bot.last_text or ""), "delete confirm shown")
    await email_delete.on_delete_confirm(
        make_callback("e:delok:0"), bot, session, state, cf
    )
    h.check("EMAIL DELETED" in (bot.last_text or ""), "delete success shown")
    h.check(cf.total_rules("z_example") == before - 1, "rule removed on Cloudflare")

    # ---- S13: manual create ----
    h.section("S13 buat email manual")
    state3 = FakeState()
    await domains.on_menu_entry(make_callback("m:create"), bot, session, state3, cf)
    await domains.on_domain_select(make_callback("d:sel:c:1"), bot, session, state3, cf)  # test.org
    await create_manual.on_manual(make_callback("c:man"), bot, session, state3)
    h.check("MANUAL EMAIL INPUT" in (bot.last_text or ""), "manual prompt shown")
    h.check((await state3.get_state()) is not None, "FSM waiting for input")
    await create_manual.on_manual_text(make_message(text="support"), bot, session, state3, cf)
    h.check("support@test.org" in (bot.last_text or ""), "manual confirm shows address")
    draft = (await state3.get_data()).get("manual_draft")
    name_id = draft[3]
    await create_manual.on_confirm(
        make_callback(f"man:ok:{name_id}"), bot, session, state3, cf
    )
    h.check("EMAILS CREATED" in (bot.last_text or ""), "manual create success")
    h.check("support@test.org" in cf.rules["z_test"], "support@test.org created on CF")

    # ---- S14: manual invalid input ----
    h.section("S14 input manual tidak valid")
    await create_manual.on_manual(make_callback("c:man"), bot, session, state3)
    await create_manual.on_manual_text(
        make_message(text="bad name with space"), bot, session, state3, cf
    )
    h.check("INVALID INPUT" in (bot.last_text or ""), "invalid input rejected")

    # ---- S15: owner-only middleware ----
    h.section("S15 owner-only access control")
    mw = OwnerOnlyMiddleware(OWNER_ID)
    called = {"owner": False, "other": False}

    async def _h_owner(event, data):
        called["owner"] = True

    async def _h_other(event, data):
        called["other"] = True

    await mw(_h_owner, make_callback("m:home"), {"event_from_user": make_user(OWNER_ID)})
    other_cb = make_callback("m:home", uid=999)
    await mw(_h_other, other_cb, {"event_from_user": make_user(999)})
    h.check(called["owner"], "owner allowed through")
    h.check(not called["other"], "non-owner blocked")
    h.check(any(a[1] for a in other_cb._acks), "non-owner got denied alert")

    # ---- S16: name generator robustness ----
    h.section("S16 generator robustness (fuzz)")
    from app.services import name_generator as ng
    from app.utils.validators import normalize_name

    ok = True
    try:
        for _ in range(50):
            batch = ng.generate_batch(10)
            if len({normalize_name(n) for n in batch}) != len(batch):
                ok = False
                break
        big = ng.generate_batch(800, max_attempts=40000)
        ok = ok and len({normalize_name(n) for n in big}) == 800
    except Exception as exc:  # pragma: no cover
        ok = False
        print("    generator raised:", exc)
    h.check(ok, "50 batches + 800-name batch unique, no crash")

    # ---- summary ----
    print(f"\n{'=' * 50}")
    print(f"RESULT: {h.passed} passed, {h.failed} failed")
    if h.failures:
        print("Failures:")
        for f in h.failures:
            print(f"  - {f}")
    print("=" * 50)
    return 0 if h.failed == 0 else 1


def main() -> int:
    return asyncio.run(run())


if __name__ == "__main__":
    sys.exit(main())
