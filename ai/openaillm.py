import os

from openai import OpenAI


def main() -> None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY environment variable.")

    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model="gpt-5-nano",
        input="你是大模型吗谁家公司的，另外你如何看待中国的ai应用开发发展",
        store=True,
    )

    print(response.output_text)


if __name__ == "__main__":
    main()
