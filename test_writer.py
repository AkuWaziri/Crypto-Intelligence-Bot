from writer import generate_intelligence

research = {
    "query": "AI agents crypto",
    "results": [
        {
            "title": "What are AI agents?",
            "content": (
                "AI agents are software systems that can reason, "
                "plan, use tools, retain context and take actions "
                "to complete tasks with limited human intervention."
            ),
            "url": "https://cloud.google.com/discover/what-are-ai-agents",
        },
        {
            "title": "What are AI Agents?",
            "content": (
                "AI agents can autonomously perform tasks by "
                "reasoning about goals, planning actions and "
                "using available tools."
            ),
            "url": "https://aws.amazon.com/what-is/ai-agents/",
        },
    ],
}

result = generate_intelligence(
    research,
    request_type="direct writer test",
)

print()
print(result)