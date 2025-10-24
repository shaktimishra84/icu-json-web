from pathlib import Path
import json, re, streamlit as st

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
    st.session_state.pop("issue_path", None)
    st.session_state.pop("node_id", None)

def guide_from_flow(flow: dict):
    nodes = {n["id"]: n for n in flow.get("nodes", []) if isinstance(n, dict) and "id" in n}
    start = flow.get("start")
    if not nodes or not start:
        st.warning("assistant_flow missing start/nodes.")
        return False
    nid = st.session_state.get("node_id", start)
    node = nodes.get(nid, {})
    st.markdown(node.get("text", ""))
    if node.get("end"):
        st.success("End of path.")
    else:
        for opt in node.get("options", []):
            lbl, nxt = opt.get("label", "Next"), opt.get("next")
            if st.button(lbl, key=f"{nid}_{lbl}"):
                st.session_state["node_id"] = nxt
                st.rerun()
    st.divider()
    cols = st.columns(2)
    with cols[0]:
        if st.button("Restart"):
            st.session_state["node_id"] = start
            st.rerun()
    with cols[1]:
        st.button("← Back", on_click=go_home, use_container_width=True)
    return True

files = list_files()
if not files:
    st.error(f"No JSONs under {DATA_DIR}"); st.stop()

if st.button("Reload files"):
    st.cache_data.clear(); st.rerun()

if "issue_path" not in st.session_state:
    st.title("ICU Assistant")
    q = st.text_input("Search issues")
    view = [p for p in files if (q.lower() in p.name.lower())] if q else files
    choice = st.selectbox("Select issue", view, index=0, format_func=pretty)
    if st.button("Start", use_container_width=True):
        st.session_state["issue_path"] = str(choice); st.session_state["node_id"] = None; st.rerun()
    st.caption(f"Loaded {len(files)} files. Add 'assistant_flow' to enable guidance.")
    st.stop()

issue = Path(st.session_state["issue_path"])
st.header(pretty(issue))
data = load_json(issue)

flow = data.get("assistant_flow")
if flow and guide_from_flow(flow):
    with st.expander("Raw JSON", expanded=False):
        st.json(data, expanded=False)
else:
    st.info("No assistant_flow found. Showing JSON.")
    st.json(data, expanded=False)
    st.button("← Back", on_click=go_home)
