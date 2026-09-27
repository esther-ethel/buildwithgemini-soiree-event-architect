# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
from zoneinfo import ZoneInfo

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types


def get_weather(query: str) -> str:
    """Simulates a web search. Use it get information on weather.

    Args:
        query: A string containing the location to get weather information for.

    Returns:
        A string with the simulated weather information for the queried location.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        return "It's 60 degrees and foggy."
    return "It's 90 degrees and sunny."


def get_current_time(query: str) -> str:
    """Simulates getting the current time for a city.

    Args:
        city: The name of the city to get the current time for.

    Returns:
        A string with the current time information.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        tz_identifier = "America/Los_Angeles"
    else:
        return f"Sorry, I don't have timezone information for query: {query}."

    tz = ZoneInfo(tz_identifier)
    now = datetime.datetime.now(tz)
    return f"The current time for query {query} is {now.strftime('%Y-%m-%d %H:%M:%S %Z%z')}"


from .tools import (
    add_guest_rsvp,
    calculate_event_expenses,
    generate_celebration_image,
    generate_celebration_video_clip,
    generate_digital_invitation,
    generate_theme_image_asset,
    get_event_details,
    get_theme_catalog_item,
    list_events,
    save_event_details,
    search_cocktail_recipes,
)


from google.adk.agents.callback_context import CallbackContext
from google.adk.memory import VertexAiMemoryBankService
from google.adk.tools.preload_memory_tool import PreloadMemoryTool

import json
from pathlib import Path
from google.adk.code_executors import AgentEngineSandboxCodeExecutor

# Read agent_engine_resource_name from deployment_metadata.json if available
agent_engine_resource_name = None
metadata_file = Path(__file__).parent.parent / "deployment_metadata.json"
if metadata_file.exists():
    try:
        with open(metadata_file) as f:
            metadata = json.load(f)
            agent_engine_resource_name = metadata.get("remote_agent_runtime_id")
    except Exception as e:
        print(f"Warning: Could not load deployment_metadata.json: {e}")

code_executor = AgentEngineSandboxCodeExecutor(
    agent_engine_resource_name=agent_engine_resource_name
)


# WRITE: after each turn, send the session to Memory Bank for extraction
async def generate_memories_callback(callback_context: CallbackContext):
    try:
        await callback_context.add_session_to_memory()
    except Exception as e:
        print(f"Memory bank callback notice: {e}")
    return None


def memory_service_builder():
    agent_engine_id = "1895582235541635072"
    if agent_engine_resource_name:
        agent_engine_id = agent_engine_resource_name.split("/")[-1]
    return VertexAiMemoryBankService(
        project="qwiklabs-gcp-02-5a2a6d61edf4",
        location="us-east1",
        agent_engine_id=agent_engine_id,
    )


from a2ui.schema.manager import A2uiSchemaManager
from a2ui.basic_catalog.provider import BasicCatalog
from .a2ui_utils import a2ui_callback

schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

a2ui_instruction = schema_manager.generate_system_prompt(
    role_description="You are Soirée, an expert Event & Celebration Architect AI helping party hosts design unforgettable theme-based celebrations.",
    workflow_description="Analyze the host's request, retrieve or save event plans via Firestore tools, compute budget splits or cocktail recipes, and return structured A2UI UI surfaces when presenting party ideas, menus, RSVPs, or event details.",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "IMAGE GENERATION DIRECTIVE: Whenever the user requests decor ideas, cake designs, theme previews, or visual elements, ALWAYS call the `generate_celebration_image` tool with a rich, detailed visual prompt to generate a photorealistic Imagen 3 celebration image and obtain a public GCS URL. Include the public URL in your A2UI Image component or Markdown output. "
        "Never point an Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "CRITICAL MEMORY FOCUS — DIETARY RESTRICTIONS & HEALTH REQUIREMENTS: "
        "Actively identify, remember, and recall all guest dietary restrictions, food allergies (peanuts, dairy, gluten, shellfish), "
        "intolerances, and beverage preferences across conversations. Always cross-reference stored dietary memories to automatically "
        "accommodate all guests safely without asking the host to repeat themselves. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
    ),
    include_schema=True,
    include_examples=True,
)


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    code_executor=code_executor,
    instruction=a2ui_instruction,
    tools=[
        PreloadMemoryTool(),
        get_weather,
        get_current_time,
        get_event_details,
        list_events,
        save_event_details,
        add_guest_rsvp,
        get_theme_catalog_item,
        calculate_event_expenses,
        generate_digital_invitation,
        generate_theme_image_asset,
        search_cocktail_recipes,
        generate_celebration_image,
        generate_celebration_video_clip,
    ],
    after_model_callback=a2ui_callback,
    after_agent_callback=generate_memories_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)
