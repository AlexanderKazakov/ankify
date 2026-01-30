import asyncio
from fastmcp import Client


async def call_tool__convert_TSV_to_Anki_deck(client):
    tsv_vocabulary="""
Hello World!\tHallo Welt!\tEng\tGe
Как дела?\t¿Cómo estás?\tRus\tSpanish
كم تبلغ من العمر؟\t你今年多大\tArabic\tChinese
"""
    note_type = "forward_and_backward"
    deck_name = "Ankify Test Deck"

    result = await client.call_tool(
        "convert_TSV_to_Anki_deck", 
        {
            "tsv_vocabulary": tsv_vocabulary, 
            "note_type": note_type, 
            "deck_name": deck_name
        }
    )
    print(result)


async def list_prompts_mcp(client):
    result = await client.list_prompts_mcp()
    for prompt in result.prompts:
        print(prompt)
        print()


async def get_prompt__vocab(client):
    result = await client.get_prompt_mcp(
        "vocab",
        {
            "language_a": "English",
            "language_b": "German",
            "note_type": "forward_and_backward",
            "custom_instructions": "Some custom instructions...",
        }
    )
    print(result.messages)
    print()


async def get_prompt__vocab__with_defaults(client):
    result = await client.get_prompt_mcp(
        "vocab",
        {}
    )
    print(result.messages)
    print()


async def get_prompt__deck(client):
    result = await client.get_prompt_mcp(
        "deck",
        {
            "deck_name": "Ankify Test Deck",
        }
    )
    print(result.messages)
    print()


async def get_prompt__deck__with_defaults(client):
    result = await client.get_prompt_mcp(
        "deck",
        {}
    )
    print(result.messages)
    print()


async def main(client):
    async with client:
        print("Listing prompts...")
        await list_prompts_mcp(client)
        print("-" * 100 + "\n\n")
        print("Getting prompt for vocab...")
        await get_prompt__vocab(client)
        print("-" * 100 + "\n\n")
        print("Getting prompt for vocab with defaults...")
        await get_prompt__vocab__with_defaults(client)
        print("-" * 100 + "\n\n")
        print("Getting prompt for deck...")
        await get_prompt__deck(client)
        print("-" * 100 + "\n\n")
        print("Getting prompt for deck with defaults...")
        await get_prompt__deck__with_defaults(client)
        print("-" * 100 + "\n\n")
        print("Calling tool to convert TSV to Anki deck...")
        await call_tool__convert_TSV_to_Anki_deck(client)
        print("-" * 100 + "\n\n")


if __name__ == "__main__":
    # Run the server with `fastmcp run src/ankify/mcp/ankify_mcp_server.py --transport http --port 8000`
    # client = Client("http://localhost:8000/mcp")

    # Test within the same process without the client-server interaction
    from .ankify_mcp_server import mcp
    client = Client(mcp)

    asyncio.run(main(client))
