# app.py — ICU Assistant with transcript logging
from pathlib import Path
import json, re, csv
from io import StringIO
from datetime import datetime
import streamlit as st

st.set_page_config(page_title="ICU Assistant", layout="wide")
DATA_DIR = Path(__file__).parent / "data" / "algorithms"

@st.cache_data(show_spinner=False)
def list_files():
    return sorted(p for p in DATA_DIR.rglob("*.json") if p.is_file())

@st.cache_data(show_spinner=False)
def load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))

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
    st.session_state["case_id"] = datetime.utcnow().strftime("case-%Y%m%d-%H%M%S")
    st.session_state["node_id"] = None
    st.session_state["log"] = []   # list of dicts

def log_step(node_id: str, node_text: str, action_label: str, next_id: str):
    st.session_state["log"].append({
        "timestamp_utc": datetime.utcnow().isoformat(timespec="seconds"),
        "node_id": node_id,
        "node_text": node_text,
        "choice": action_label,
        "next_node": next_id
    })

def download_csv(log):
    buf = StringIO()
    writer = csv.DictWriter(buf, fieldnames=["timestamp_utc","node_id","node_text","choice","next_node"])
    writer.writeheader()
    writer.writerows(log)
    return buf.getvalue()

files = list_files()
if not files:
    st.error(f"No JSONs under {DATA_DIR}"); st.stop()

# home screen
if "issue_path" not in st.session_state:
    st.title("ICU Assistant")
    q = st.text_input("search issues")
    view = [p for p in files if (q.lower() in p.name.lower())] if q else files
    choice = st.selectbox("select issue", view, index=0, format_func=pretty)
    c1, c2 = st.columns([1,1])
    with c1: resident = st.text_input("resident name (optional)")
    with c2: patient_id = st.text_input("patient id/case id (optional)")
    if st.button("start"):
        start_case(choice, resident, patient_id)
        st.rerun()
    st.caption(f"loaded {len(files)} files")
    st.stop()

# guide screen
issue = Path(st.session_state["issue_path"])
st.button("← back", on_click=go_home)
st.header(pretty(issue))

data = load_json(issue)
flow = data.get("assistant_flow")

if not flow:
    st.info("no assistant_flow found. showing JSON.")
    st.json(data, expanded=False)
    st.stop()

nodes = {n["id"]: n for n in flow.get("nodes", []) if isinstance(n, dict) and "id" in n}
start = flow.get("start")
if "node_id" not in st.session_state or st.session_state["node_id"] is None:
    st.session_state["node_id"] = start

nid = st.session_state["node_id"]
node = nodes.get(nid, {})

# main step
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

# transcript panel
with st.expander("transcript (choices made)", expanded=True):
    if not st.session_state.get("log"):
        st.write("no choices yet")
    else:
        for i, row in enumerate(st.session_state["log"], 1):
            st.write(f"{i}. [{row['timestamp_utc']}] at {row['node_id']} → chose “{row['choice']}”")
        st.caption("download the full transcript for teaching or audit")

    meta = {
        "case_id": st.session_state.get("case_id",""),
        "issue": pretty(issue),
        "resident": st.session_state.get("resident",""),
        "patient_id": st.session_state.get("patient_id",""),
        "log": st.session_state.get("log", [])
    }
    json_blob = json.dumps(meta, ensure_ascii=False, indent=2)
    csv_blob = download_csv(meta["log"])

    c1, c2 = st.columns(2)
    with c1:
        st.download_button("download transcript (json)", data=json_blob,
                           file_name=f"{st.session_state.get('case_id','case')}.json",
                           mime="application/json")
    with c2:
        st.download_button("download transcript (csv)", data=csv_blob,
                           file_name=f"{st.session_state.get('case_id','case')}.csv",
                           mime="text/csv")

# footer controls
c1, c2 = st.columns(2)
with c1:
    if st.button("restart case"):
        st.session_state["node_id"] = start
        st.session_state["log"] = []
        st.rerun()
with c2:
    if st.button("new case"):
        go_home()
        st.rerun()
