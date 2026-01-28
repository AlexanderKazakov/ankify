import asyncio
from fastmcp import Client


# Run the server with `fastmcp run src/ankify/mcp/ankify_mcp_server.py --transport http --port 8000`
client = Client("http://localhost:8000/mcp")


async def call_tool__convert_TSV_to_Anki_deck():
    tsv_vocabulary="""
Hello World!\tHallo Welt!\tEng\tGe
Как дела?\t¿Cómo estás?\tRus\tSpanish
كم تبلغ من العمر؟\t你今年多大\tArabic\tChinese
"""
    note_type = "forward_and_backward"
    deck_name = "Ankify Test Deck"

    async with client:
        result = await client.call_tool(
            "convert_TSV_to_Anki_deck", 
            {
                "tsv_vocabulary": tsv_vocabulary, 
                "note_type": note_type, 
                "deck_name": deck_name
            }
        )
        print(result)


async def list_prompts_mcp():
    async with client:
        result = await client.list_prompts_mcp()
        for prompt in result.prompts:
            print(prompt)
            print()


async def get_prompt__vocab():
    async with client:
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


async def main():
    await list_prompts_mcp()
    print("-" * 100 + "\n\n")
    await get_prompt__vocab()
    print("-" * 100 + "\n\n")
    await call_tool__convert_TSV_to_Anki_deck()


if __name__ == "__main__":
    asyncio.run(main())
