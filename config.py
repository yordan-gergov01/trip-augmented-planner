USER_AGENT = "trip-planner/1.0 (yordangergov@xype.io)"
HEADERS = {"User-Agent": USER_AGENT}

INTEREST_TO_TAGS = {
    "museums":   [("tourism", "museum|gallery")],
    "food":      [("amenity", "restaurant|cafe|fast_food")],
    "outdoors":  [("leisure", "park|nature_reserve"), ("natural", "peak|beach")],
    "history":   [("historic", "monument|castle|ruins|memorial")],
    "shopping":  [("shop", "mall|clothes|market")],
    "nightlife": [("amenity", "bar|pub|nightclub")],
    "religion":  [("amenity", "place_of_worship")],
    "transport": [("public_transport", "station")],
}

TOOLS = [
    {
        "type": "function",
        "name": "search_pois",
        "description": "Search for Points of Interest in a city based on user interests using OpenStreetMap.",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "The city to search in."
                },
                "interests": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of interest categories e.g. museums, food, outdoors."
                },
                "radius": {
                    "type": "integer",
                    "description": "Search radius in meters. Use 2000 as default."
                }
            },
            "required": ["city", "interests", "radius"],
            "additionalProperties": False
        },
        "strict": True
    },
    {
        "type": "function",
        "name": "retrieve_guides",
        "description": "Retrieve relevant travel guide context from Wikivoyage for a city using RAG.",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "The city to retrieve travel guide context for."
                },
                "query": {
                    "type": "string",
                    "description": "The search query to find relevant guide sections."
                }
            },
            "required": ["city", "query"],
            "additionalProperties": False
        },
        "strict": True
    }
]