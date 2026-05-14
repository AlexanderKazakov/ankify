import asyncio
from fastmcp import Client


def prompt_text(result):
    content = result.messages[0].content
    if hasattr(content, "text"):
        return content.text
    return str(content)


async def call_tool__convert_TSV_to_Anki_deck(client):
    tsv_vocabulary = """
Hello World!\tHallo Welt!\tEng\tGe
Как дела?\t¿Cómo estás?\tRus\tSpanish
كم تبلغ من العمر؟\t你今年多大\tArabic\tChinese
"""
    note_type = "basic_and_reversed"
    deck_name = "Ankify Test Deck"

    result = await client.call_tool(
        "convert_TSV_to_Anki_deck",
        {
            "tsv_vocabulary": tsv_vocabulary,
            "note_type": note_type,
            "deck_name": deck_name,
        },
    )
    print(result)


async def list_prompts(client):
    result = await client.list_prompts()
    for prompt in result:
        print(prompt)
        print()


async def get_prompt__vocab(client):
    result = await client.get_prompt(
        "vocab",
        {
            "language_studied": "English",
            "language_known": "German",
            "note_type": "basic_and_reversed",
            "custom_instructions": "Some custom instructions...",
        },
    )
    print(prompt_text(result))
    print()


async def get_prompt__vocab__with_defaults(client):
    result = await client.get_prompt("vocab", {})
    print(prompt_text(result))
    print()


async def get_prompt__deck(client):
    result = await client.get_prompt(
        "deck",
        {
            "deck_name": "Ankify Test Deck",
        },
    )
    print(prompt_text(result))
    print()


async def get_prompt__deck__with_defaults(client):
    result = await client.get_prompt("deck", {})
    print(prompt_text(result))
    print()


async def main(client):
    async with client:
        print("Listing prompts...")
        await list_prompts(client)
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
