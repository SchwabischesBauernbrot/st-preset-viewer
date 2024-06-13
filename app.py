import gradio as gr
import requests
import json
from numbers import Real

builtin_pairs = [
    ("Chat Examples", "dialogueExamples"),
    ("Chat History", "chatHistory"),
    ("World Info (after)", "worldInfoAfter"),
    ("World Info (before)", "worldInfoBefore"),
    ("Enhance Definitions", "enhanceDefinitions"),
    ("Char Description", "charDescription"),
    ("Char Personality", "charPersonality"),
    ("Scenario", "scenario"),
    ("Persona Description", "personaDescription"),
    ("JB", "jailbreak"),
    ("NSFW", "nsfw"),
    ("Main Prompt", "main"),
]
builtin_prompts = [{
    "name": x[0],
    "identifier": x[1],
    "system_prompt": True,
    "marker": True,
} for x in builtin_pairs]

# Not meant to 100% validate a preset. Just enough that the code
# that renders it won't crash trying to access an invalid key.
class Validator:
    def __init__(self, obj):
        self.valid = True
        self.obj = obj

    def try_validate_key(self, key, ty):
        if key not in self.obj:
            return False
        if not isinstance(self.obj[key], ty):
            return False
        return True
    
    def validate_key(self, key, ty):
        r = self.try_validate_key(key, ty)
        if not r:
            self.valid = False
        return r
    
    def validate_key_if_present(self, key, ty):
        if key in self.obj and not isinstance(self.obj[key], ty):
            self.valid = False

    def validate_keys_if_present(self, keys, ty):
        for k in keys:
            self.validate_key_if_present(k, ty)

    def validate_prompt(self):
        self.validate_key("identifier", bool)
        self.validate_key("name", str)
        self.validate_keys_if_present([
            "injection_position",
            "injection_depth",
        ], int)
        self.validate_keys_if_present([
            "role",
            "content",
        ], str)
        self.validate_keys_if_present([
            "system_prompt",
            "marker",
            "forbid_overrides",
        ], bool)

    def validate_prompt_order(self):
        if not self.try_validate_key("character_id", str):
            self.validate_key("character_id", int)
        if self.validate_key("order", list):
            if not Validator.is_valid_prompt_order_list(self.obj["order"]):
                self.valid = False

    def validate_prompt_order_list(self):
        for s in self.obj:
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
        known_prompt_ids = set(x[1] for x in builtin_pairs)
        if self.validate_key("prompts", list):
            for prompt in self.obj["prompts"]:
                if not Validator.is_valid_prompt(prompt):
                    continue
                known_prompt_ids.add(prompt["identifier"])
        seen_cid0 = False
        if self.validate_key("prompt_order", list) and len(self.obj["prompt_order"]) > 0 and isinstance(self.obj["prompt_order"][0], dict):
            for order in self.obj["prompt_order"]:
                # FIXME: the identifier check doesn't work?
                if Validator.is_valid_prompt_order(order) and order["character_id"] == 100001: #and all(o["identifier"] in known_prompt_ids for o in order["order"]):
                    seen_cid0 = True
            # if Validator.is_valid_prompt_order_list(self.obj["prompt_order"]) and all(lambda o: o["identifier"] in known_prompt_ids for o in self.obj["prompt_order"]):
            #     seen_cid0 = True
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
    def is_valid_prompt_order_list(cls, prompt_order_list):
        v = cls(prompt_order_list)
        v.validate_prompt_order_list()
        return v.valid

    @classmethod
    def is_valid_ordering(cls, ordering):
        v = cls(ordering)
        v.validate_ordering()
        return v.valid

def maybe_convert_to_original_format(obj):
    if obj.get("version") != 1:
        return obj, False
    # Synthesize a traditional preset
    return {
        "prompts": obj["data"]["prompts"] + builtin_prompts,
        "prompt_order": [{
            "character_id": 100001,
            "order": obj["data"]["prompt_order"],
        }]
    }, True

CONVERT_MESSAGE = "This preset was converted from version 1 to the traditional format, there may be inconsistencies."

def load_from_file(path):
    with open(path, "r") as f:
        try:
            obj = json.load(f)
        except Exception:
            raise gr.Error("File is not valid JSON")
            return None, True
    obj, modified = maybe_convert_to_original_format(obj)
    if not Validator.is_valid_preset(obj):
        raise gr.Error("File is not a valid preset")
        return None, True
    return gr.update(selected=1), obj, CONVERT_MESSAGE if modified else None

def load_from_url(url):
    resp = requests.get(url)
    if not resp.ok:
        raise gr.Error("Failed to load URL")
        return None, True
    try:
        obj = json.loads(resp.text)
    except Exception:
        raise gr.Error("URL is not valid JSON")
        return None, True
    obj, modified = maybe_convert_to_original_format(obj)
    if not Validator.is_valid_preset(obj):
        raise gr.Error("URL is not a valid preset")
        return None, True
    return gr.update(selected=1), obj, CONVERT_MESSAGE if modified else None

def render_prompt(prompt, enabled=True):
    with gr.Accordion(prompt["name"] + ("" if enabled else " (DISABLED)"), open=enabled or prompt.get("marker", False)):
        if prompt.get("marker", False):
            gr.Markdown(f"This is a marker ({prompt['identifier']})")
        else:
            gr.Markdown(f"Role: {prompt['role'] or 'system'}")
            if "injection_position" in prompt and prompt["injection_position"] == 1 and "injection_depth" in prompt:
                gr.Markdown(f"Injection depth: {prompt['injection_depth']} (absolute)")
            gr.Code(prompt["content"], container=False)

with gr.Blocks() as demo:
    # preset_error = gr.State(False)
    preset = gr.State(None)
    load_extra = gr.State(None)
    
    gr.Markdown("# SillyTavern preset viewer")

    with gr.Tabs() as tabs:
        with gr.TabItem("Upload", id=0):
            file = gr.File(label="Upload a preset (.json)", file_types=[".json"])
            file.upload(fn=load_from_file, inputs=[file], outputs=[tabs, preset, load_extra])
            url_input = gr.Textbox(label="Enter a URL to a preset (.json) - press Enter to submit")
            url_input.submit(fn=load_from_url, inputs=[url_input], outputs=[tabs, preset, load_extra])
        with gr.TabItem("Viewer", id=1):
            @gr.render(inputs=[preset, load_extra])
            def render_preset(preset, load_extra):
                if preset is None:
                    gr.Markdown("No preset loaded, enter a URL or upload a file")
                else:
                    gr.Markdown("Preset loaded and validated")
                    if load_extra is not None:
                        gr.Markdown(load_extra)
                    prompt_map = {p["identifier"]: p for p in builtin_prompts+preset["prompts"]}
                    gr.Markdown("# Preset")
                    for order in (next(o for o in preset["prompt_order"] if o["character_id"] == 100001)["order"] if isinstance(preset["prompt_order"], list) else preset["prompt_order"]):
                        prompt = prompt_map[order["identifier"]]
                        render_prompt(prompt, order["enabled"])
                    gr.Markdown("# All prompts")
                    with gr.Accordion("All prompts", open=False):
                        for prompt in prompt_map.values():
                            render_prompt(prompt)

    
demo.launch()