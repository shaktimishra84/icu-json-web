from pathlib import Path
import json, re, csv
from io import StringIO
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import streamlit as st

# Optional: Google Sheets logging
try:
    import gspread
    from google.oauth2.service_account import Credentials
    GS_READY = True
except Exception:
    GS_READY = False

TIMEZONE = ZoneInfo("Asia/Kolkata")
DATA_DIR = Path(__file__).parent / "data" / "algorithms"

st.set_page_config(page_title="ICU Assistant", layout="wide")
st.caption("build: 2025-10-24 20:35 IST")

# ---------- Data helpers ----------
@st.cache_data(show_spinner=False)
def list_files():
    return sorted(p for p in DATA_DIR.rglob("*.json") if p.is_file())

@st.cache_data(show_spinner=False)
def load_json(p: Path):
    txt = p.read_text(encoding="utf-8")
    return json.loads(txt)

def pretty(p: Path) -> str:
    n = re.sub(r"\.json$", "", p.name, flags=re.I)
    n = re.sub(r"\.(final|fixed|clean|polished|v\d+)+$", "", n, flags=re.I)
    return re.sub(r"^\d+_", "", n).replace("_", " ")

def go_home():
    st.session_state.clear()

def start_case(issue_path: Path, resident: str, patient_id: str):
    st.session_state["issue_path"] = str(issue_path)
    st.session_state["resident"] = resident.strip()
    st.session_state["patient_id"] = patient_id.strip()
    st.session_state["case_id"] = datetime.now(TIMEZONE).strftime("case-%Y%m%d-%H%M%S-IST")
    st.session_state["node_id"] = None
    st.session_state["log"] = []   # list of dicts

def log_step(node_id: str, node_text: str, action_label: str, next_id: str):
    st.session_state["log"].append({
        "timestamp_ist": datetime.now(TIMEZONE).isoformat(timespec="seconds"),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "node_id": node_id,
        "node_text": node_text,
        "choice": action_label,
        "next_node": next_id
    })

def csv_from_rows(rows: list, headers: list):
    s = StringIO()
    w = csv.DictWriter(s, fieldnames=headers)
    w.writeheader()
    for r in rows:
        w.writerow({k: r.get(k, "") for k in headers})
    return s.getvalue()

def nodes_table_from_flow(flow: dict):
    nodes = flow.get("nodes", [])
    out = []
    for n in nodes:
        opts = ", ".join([o.get("label","") for o in n.get("options", [])]) if n.get("options") else ""
        out.append({"id": n.get("id",""), "end": bool(n.get("end", False)), "text": n.get("text",""), "options": opts})
    return out

# ---------- Google Sheets ----------
def _gs_client():
    if not GS_READY: return None, None
    sa_json = st.secrets.get("GSHEETS_SA_JSON", None)
    sheet_url = st.secrets.get("GSHEET_URL", None)
    if not sa_json or not sheet_url:
        return None, None
    creds = Credentials.from_service_account_info(
        json.loads(sa_json),
        scopes=["https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"]
    )
    gc = gspread.authorize(creds)
    return gc, sheet_url

def save_log_to_gsheet(meta: dict):
    gc, sheet_url = _gs_client()
    if not gc:
        st.warning("Google Sheets not configured in Secrets.")
        return False
    sh = gc.open_by_url(sheet_url)
    try:
        ws = sh.worksheet("transcripts")
    except Exception:
        ws = sh.add_worksheet(title="transcripts", rows=1000, cols=12)
        ws.append_row(["case_id","issue","resident","patient_id",
                       "timestamp_ist","timestamp_utc","node_id","node_text","choice","next_node"])
    rows = []
    for r in meta["log"]:
        rows.append([
            meta.get("case_id",""),
            meta.get("issue",""),
            meta.get("resident",""),
            meta.get("patient_id",""),
            r.get("timestamp_ist",""),
            r.get("timestamp_utc",""),
            r.get("node_id",""),
            r.get("node_text",""),
            r.get("choice",""),
            r.get("next_node",""),
        ])
    if rows:
        ws.append_rows(rows, value_input_option="RAW")
    return True

# ---------- App ----------
files = list_files()
if not files:
    st.error(f"No JSONs under {DATA_DIR}"); st.stop()

if st.button("Reload files"):
    st.cache_data.clear(); st.rerun()

# Home
if "issue_path" not in st.session_state:
    st.title("ICU Assistant")
    q = st.text_input("search issues")
    view = [p for p in files if (q.lower() in p.name.lower())] if q else files
    choice = st.selectbox("select issue", view, index=0, format_func=pretty)
    c1, c2 = st.columns(2)
    with c1: resident = st.text_input("resident name (optional)")
    with c2: patient_id = st.text_input("patient id/case id (optional)")
    if st.button("start"):
        start_case(choice, resident, patient_id)
        st.rerun()
    st.caption(f"loaded {len(files)} files. add 'assistant_flow' to enable guidance.")
    st.stop()

# Guide
issue = Path(st.session_state["issue_path"])
st.button("← back", on_click=go_home)
st.header(pretty(issue))

try:
    data = load_json(issue)
except Exception as e:
    st.error(f"JSON load/parse error: {e}")
    st.code(issue.read_text(encoding="utf-8"), language="json")
    st.stop()

flow = data.get("assistant_flow")
if not flow:
    st.info("no assistant_flow found. showing raw JSON.")
    st.json(data, expanded=False)
    st.stop()

nodes = {n["id"]: n for n in flow.get("nodes", []) if isinstance(n, dict) and "id" in n}
start = flow.get("start")
if not nodes or not start:
    st.warning("assistant_flow missing start/nodes")
    st.json(flow); st.stop()

if "node_id" not in st.session_state or st.session_state["node_id"] is None:
    st.session_state["node_id"] = start

nid = st.session_state["node_id"]
node = nodes.get(nid, {})

st.markdown(node.get("text", ""))

if node.get("end"):
    st.success("end of path")
else:
    for opt in node.get("options", []):
        lbl, nxt = opt.get("label", "Next"), opt.get("next")
        if st.button(lbl, key=f"{nid}_{lbl}"):
            log_step(nid, node.get("text",""), lbl, nxt)
            st.session_state["node_id"] = nxt
            st.rerun()

st.divider()

with st.expander("nodes (reference)", expanded=False):
    tbl = nodes_table_from_flow(flow)
    st.table(tbl)
    nodes_csv = csv_from_rows(tbl, ["id","end","text","options"])
    st.download_button("download nodes (csv)", data=nodes_csv,
                       file_name=f"{issue.stem}_nodes.csv", mime="text/csv")

with st.expander("transcript (choices made)", expanded=True):
    log = st.session_state.get("log", [])
    if not log:
        st.write("no choices yet")
    else:
        for i, r in enumerate(log, 1):
            st.write(f"{i}. [{r['timestamp_ist']}] at {r['node_id']} → “{r['choice']}”")
        meta = {
            "case_id": st.session_state.get("case_id",""),
            "issue": pretty(issue),
            "resident": st.session_state.get("resident",""),
            "patient_id": st.session_state.get("patient_id",""),
            "log": log
        }
        json_blob = json.dumps(meta, ensure_ascii=False, indent=2)
        csv_blob = csv_from_rows(log, ["timestamp_ist","timestamp_utc","node_id","node_text","choice","next_node"])
        c1, c2, c3 = st.columns(3)
        with c1:
            st.download_button("download transcript (json)", data=json_blob,
                               file_name=f"{meta['case_id'] or 'case'}.json", mime="application/json")
        with c2:
            st.download_button("download transcript (csv)", data=csv_blob,
                               file_name=f"{meta['case_id'] or 'case'}.csv", mime="text/csv")
        with c3:
            if GS_READY and st.button("save to google sheet"):
                ok = save_log_to_gsheet(meta)
                if ok: st.success("saved to Google Sheet")
            elif not GS_READY:
                st.caption("install gspread + google-auth to enable Google Sheets save.")
            else:
                st.caption("set Secrets: GSHEETS_SA_JSON and GSHEET_URL to enable save.")

c1, c2 = st.columns(2)
with c1:
    if st.button("restart case"):
        st.session_state["node_id"] = start
        st.session_state["log"] = []
        st.rerun()
with c2:
    if st.button("new case"):
        go_home(); st.rerun()
