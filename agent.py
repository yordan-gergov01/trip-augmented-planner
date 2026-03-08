import json
from maps import search_pois
from rag import get_travel_context
from config import TOOLS


def execute_tool(tool_name, tool_args, tool_state):
    if tool_name == "search_pois":
        city = tool_args["city"]
        interests = tuple(tool_args["interests"])
        radius = tool_args.get("radius", 2000)

        pois = search_pois(city, interests, radius)
        tool_state["pois"].extend(pois)
        tool_state["city"] = city
        return {"found": len(pois), "pois": pois}

    elif tool_name == "retrieve_guides":
        city  = tool_args["city"]
        query = tool_args["query"]

        chunks = get_travel_context(city, query)
        tool_state["chunks"].extend(chunks)
        return {"found": len(chunks), "chunks": chunks}

    return {"error": f"Unknown tool: {tool_name}"}


def run_agent(client, user_request, max_steps=10):
    tool_state = {"pois": [], "chunks": [], "city": None}
    trace = []

    system_prompt = """You are an expert travel planner AI agent.
Your job is to create a personalized itinerary for the user.

You have access to two tools:
1. search_pois — finds real Points of Interest from OpenStreetMap
2. retrieve_guides — fetches relevant travel context from Wikivoyage

IMPORTANT RULES:
- Always call search_pois first to find real POIs
- Only include POIs in the itinerary that were actually returned by search_pois
- Use retrieve_guides to enrich your itinerary with local tips and context
- Structure the final itinerary by day with clear timings
- Never hallucinate places that weren't returned by the tools"""

    input_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_request}
    ]

    for step in range(max_steps):
        trace.append(f"**Step {step + 1}** — Calling model...")

        response = client.responses.create(
            model="gpt-4.1-mini",
            input=input_messages,
            tools=TOOLS,
        )

        if not response.output:
            trace.append("No output from model.")
            break

        tool_calls = [item for item in response.output if item.type == "function_call"]
        text_items = [item for item in response.output if item.type == "message"]

        # No tool calls — model is done
        if not tool_calls:
            final_text = ""
            for item in text_items:
                for content in item.content:
                    if hasattr(content, "text"):
                        final_text += content.text
            trace.append("✅ Agent finished.")
            return final_text, tool_state, trace

        for item in response.output:
            input_messages.append(item)

        for tool_call in tool_calls:
            tool_name = tool_call.name
            tool_args = json.loads(tool_call.arguments)

            trace.append(f"🔧 Tool: `{tool_name}` → `{tool_args}`")
            result = execute_tool(tool_name, tool_args, tool_state)
            trace.append(f"✅ `{tool_name}` returned {result.get('found', 0)} results.")

            input_messages.append({
                "type": "function_call_output",
                "call_id": tool_call.call_id,
                "output":  json.dumps(result)
            })

    trace.append("⚠️ Max steps reached.")
    return "Could not generate itinerary within step limit.", tool_state, trace