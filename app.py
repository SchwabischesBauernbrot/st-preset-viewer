import gradio as gr
import requests
import json
from numbers import Real

# Not meant to 100% validate a preset. Just enough that the code
# that renders it won't crash trying to access an invalid key.
class Validator:
    def __init__(self, obj):
        self.valid = True
        self.obj = obj

    def validate_key(self, key, ty):
        if key not in self.obj:
            self.valid = False
            return False
        if not isinstance(self.obj[key], ty):
            self.valid = False
            return False
        return True
    
    def validate_key_if_present(self, key, ty):
        if key in self.obj and not isinstance(self.obj[key], ty):
            self.valid = False

    def validate_keys_if_present(self, keys, ty):
        for k in keys:
            self.validate_key_if_present(k, ty)

    def validate_prompt(self):
        self.validate_key("identifier", bool)
        self.validate_keys_if_present([
            "injection_position",
            "injection_depth",
        ], int)
        self.validate_keys_if_present([
            "name",
            "role",
            "content",
        ], str)
        self.validate_keys_if_present([
            "system_prompt",
            "marker",
            "forbid_overrides",
        ], bool)

    def validate_prompt_order(self):
        self.validate_key("character_id", str)
        if self.validate_key("order", list):
            for s in self.obj["order"]:
                if not Validator.is_valid_ordering(s):
                    self.valid = False

    def validate_ordering(self):
        self.validate_key("identifier", str)
        self.validate_key("enabled", bool)
    
    def validate_preset(self):
        self.validate_keys_if_present([
            "impersonation_prompt",
            "new_chat_prompt",
            "new_group_chat_prompt",
            "new_example_chat_prompt",
            "continue_nudge_prompt",
            "wi_format",
            "scenario_format",
            "personality_format",
            "group_nudge_prompt",
            "assistant_prefill",
            "human_sysprompt_message",
            "continue_postfix",
        ], str)
        self.validate_keys_if_present([
            "claude_use_sysprompt",
            "squash_system_messages",
            "continue_prefill",
        ], bool)
        self.validate_keys_if_present([
            "temperature",
            "frequency_penalty",
            "presence_penalty",
            "count_penalty",
            "top_p",
            "top_k",
            "top_a",
            "min_p",
            "repetition_penalty",
        ], Real)
        self.validate_key_if_present("names_behavior", int)
        known_prompt_ids = set()
        if self.validate_key("prompts", list):
            for prompt in self.obj["prompts"]:
                if not Validator.is_valid_prompt(prompt):
                    continue
                known_prompt_ids.add(prompt["identifier"])
        seen_cid0 = False
        if self.validate_key("prompt_order", list):
            for order in self.obj["prompt_order"]:
                if Validator.is_valid_prompt_order(order):
                    and order["character_id"] == "0"
                    and all(lambda o: o["identifier"] in known_prompt_ids for o in order["order"]):
                    seen_cid0 = True
        if not seen_cid0:
            self.valid = False

    @classmethod
    def is_valid_preset(cls, preset):
        v = cls(preset)
        v.validate_preset()
        return v.valid

    @classmethod
    def is_valid_prompt(cls, prompt):
        v = cls(prompt)
        v.validate_prompt()
        return v.valid

    @classmethod
    def is_valid_prompt_order(cls, prompt_order):
        v = cls(prompt_order)
        v.validate_prompt_order()
        return v.valid

    @classmethod
    def is_valid_ordering(cls, ordering):
        v = cls(ordering)
        v.validate_ordering()
        return v.valid

def load_from_file(path):
    with open(path, "r") as f:
        try:
            obj = json.load(f)
        except Exception:
            return None, True
    if not Validator.is_valid_preset(obj):
        return None, True
    return obj, False

def load_from_url(url):
    resp = requests.get(url)
    if not resp.ok:
        return None, True
    try:
        obj = json.loads(resp.text)
    except Exception:
        return None, True
    if not Validator.is_valid_preset(obj):
        return None, True
    return obj, False

with gr.Blocks() as demo:
    preset_error = gr.State(False)
    preset = gr.State(None)
    
    gr.Markdown("# SillyTavern preset viewer")

    with gr.Tabs() as tabs:
        with gr.TabItem("Upload", id=0):
            file = gr.File(label="Upload a preset (.json)", file_types=[".json"])
            file.input(fn=load_from_file, inputs=[file], outputs=[preset, preset_error])
            url_input = gr.Textbox(label="Enter a URL to a preset (.json) - press Enter to submit")
            url_input.submit(fn=load_from_url, inputs=[url_input], outputs=[preset, preset_error])
        with gr.TabItem("Viewer", id=1):
            @gr.render(inputs=[preset_error, preset])
            def render_preset(preset_error, preset):
                if preset_error:
                    gr.Markdown("Error loading preset")
                    return
                if preset is None:
                    gr.Markdown("No preset loaded, enter a URL or upload a file")
                else:
                    gr.Markdown("Preset loaded and validated")
                    gr.Json(preset)
    
demo.launch()