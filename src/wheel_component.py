from pathlib import Path
import streamlit.components.v1 as components

_wheel = components.declare_component("destiny_wheel", path=str(Path(__file__).parent / "wheel"))

def wheel(titles, batch_id, posters=None):
    if len(titles) != 3:
        raise ValueError("The wheel requires exactly three titles.")
    return _wheel(titles=titles, posters=posters or [], batch_id=batch_id, key=f"wheel_{batch_id}", default=None)
