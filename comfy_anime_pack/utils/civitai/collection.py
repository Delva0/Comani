"""
Civitai Collection utilities.
Fetch and export models from Civitai collections.
"""
import json
import os
import re
import time

import requests
import yaml

# Civitai model type to ComfyUI directory mapping
MODEL_TYPE_MAP = {
    "LORA": "loras",
    "LoCon": "loras",
    "DoRA": "loras",
    "Checkpoint": "checkpoints",
    "TextualInversion": "embeddings",
    "VAE": "vae",
    "ControlNet": "controlnet",
    "Upscaler": "upscale_models",
    "Poses": "poses",
    "Wildcards": "wildcards",
    "MotionModule": "animatediff_models",
    "AestheticGradient": "aesthetic_embeddings",
}


def get_collection_items(collection_id: int, api_token: str | None = None) -> list[dict]:
    """
    Get items from a Civitai collection.
    Requires API token for private collections or TRPC endpoint.
    """
    api_url = "https://civitai.com/api/trpc/collection.getAllCollectionItems"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/json",
    }
    if api_token:
        headers["Authorization"] = f"Bearer {api_token}"

    all_items = []
    print(f"Fetching collection {collection_id}...\n")

    if not api_token:
        print("⚠️  Warning: No API Token provided, collection access may require authentication")
        print("   Set env CIVITAI_API_TOKEN or pass api_token parameter")
        print("   Get token: https://civitai.com/user/account -> API Keys\n")

    cursor = None
    page = 1

    while True:
        try:
            input_obj = {"collectionId": collection_id}
            if cursor:
                input_obj["cursor"] = cursor
            params = {"input": json.dumps({"json": input_obj})}

            response = requests.get(api_url, params=params, headers=headers)

            if response.status_code == 401:
                print("❌ Auth failed: Valid API Token required")
                print("   Set env: export CIVITAI_API_TOKEN='your_token_here'")
                return all_items

            if response.status_code != 200:
                print(f"Request failed, status: {response.status_code}")
                print(f"Response: {response.text[:500]}")
                return all_items

            data = response.json()

            if "error" in data:
                error_msg = data.get("error", {}).get("json", {}).get("message", "Unknown error")
                print(f"❌ API error: {error_msg}")
                return all_items

            json_data = data.get("result", {}).get("data", {}).get("json", {})
            items = json_data.get("collectionItems", []) if isinstance(json_data, dict) else []
            next_cursor = json_data.get("nextCursor") if isinstance(json_data, dict) else None

            if not items:
                if page == 1:
                    print("Collection empty or inaccessible")
                break

            for item in items:
                item_type = item.get("type", "unknown").lower()
                name = "Unknown"
                url = "#"
                item_id = item.get("id")
                data_obj = item.get("data", {})

                if item_type == "model":
                    name = data_obj.get("name", f"Model ID: {item_id}")
                    model_id = data_obj.get("id", item_id)
                    url = f"https://civitai.com/models/{model_id}"
                elif item_type == "image":
                    image_id = data_obj.get("id", item_id)
                    name = f"Image ID: {image_id}"
                    url = f"https://civitai.com/images/{image_id}"
                elif item_type == "post":
                    post_id = data_obj.get("id", item_id)
                    name = data_obj.get("title") or f"Post ID: {post_id}"
                    url = f"https://civitai.com/posts/{post_id}"
                elif item_type == "article":
                    article_id = data_obj.get("id", item_id)
                    name = data_obj.get("title") or f"Article ID: {article_id}"
                    url = f"https://civitai.com/articles/{article_id}"

                all_items.append({"type": item_type, "name": name, "url": url})
                print(f"[{item_type.upper()}] {name}")

            if not next_cursor:
                break

            cursor = next_cursor
            page += 1
            time.sleep(0.5)

        except requests.exceptions.RequestException as e:
            print(f"Network error: {e}")
            break
        except json.JSONDecodeError as e:
            print(f"JSON parse error: {e}")
            break
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
            break

    print(f"\nDone! Found {len(all_items)} items.")
    return all_items


def get_model_info(model_id: str | int, api_token: str | None = None) -> dict | None:
    """Fetch model info from Civitai API."""
    from .api import get_model_info as api_get_model_info
    return api_get_model_info(model_id)


def export_models(
    collection_id: int,
    output_file: str = "collection_models.yml",
    prefix: str = "",
    api_token: str | None = None
) -> dict:
    """
    Export collection models to a YML dict grouped by model type.
    Example: export_models(123456, prefix="my_") generates {loras: [{url: ..., filename: my_xxx.safetensors}]}
    """
    api_token = api_token or os.environ.get("CIVITAI_API_TOKEN")
    items = get_collection_items(collection_id, api_token)

    model_items = [item for item in items if item["type"] == "model"]
    print(f"\nFetching details for {len(model_items)} models...")

    result: dict[str, list[dict]] = {}

    for i, item in enumerate(model_items, 1):
        url = item["url"]
        match = re.search(r"/models/(\d+)", url)
        if not match:
            print(f"  [{i}/{len(model_items)}] Skipping invalid URL: {url}")
            continue

        model_id = match.group(1)
        print(f"  [{i}/{len(model_items)}] Fetching model {model_id}: {item['name'][:40]}...")

        info = get_model_info(model_id, api_token)
        if not info:
            continue

        model_type = info.get("type", "Unknown")
        subdir = MODEL_TYPE_MAP.get(model_type, "other")

        versions = info.get("modelVersions", [])
        if not versions:
            print(f"    ⚠️  No version info")
            continue

        files = versions[0].get("files", [])
        if not files:
            print(f"    ⚠️  No file info")
            continue

        original_filename = files[0].get("name", f"model_{model_id}.safetensors")
        filename = f"{prefix}{original_filename}" if prefix else original_filename

        if subdir not in result:
            result[subdir] = []

        result[subdir].append({
            "url": url,
            "filename": filename,
        })

        time.sleep(0.3)

    # Save to YML
    with open(output_file, "w", encoding="utf-8") as f:
        yaml.dump(result, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    print(f"\n✅ Export complete! Saved to {output_file}")
    for subdir, models in result.items():
        print(f"   {subdir}: {len(models)} models")

    return result


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Civitai Collection Tools")
    parser.add_argument("collection_id", type=int, help="Collection ID to fetch")
    parser.add_argument("--export", type=str, choices=["model"], help="Export type: model")
    parser.add_argument("--prefix", type=str, default="", help="Filename prefix for exported models")
    parser.add_argument("--output", type=str, default="collection_models.yml", help="Output YML file")
    args = parser.parse_args()

    api_token = os.environ.get("CIVITAI_API_TOKEN")

    if args.export == "model":
        export_models(
            args.collection_id,
            output_file=args.output,
            prefix=args.prefix,
            api_token=api_token,
        )
    else:
        items = get_collection_items(args.collection_id, api_token=api_token)
        if items:
            with open("collection_list.txt", "w", encoding="utf-8") as f:
                for item in items:
                    f.write(f"[{item['type']}] {item['name']}: {item['url']}\n")
            print(f"\nResults saved to collection_list.txt")


if __name__ == "__main__":
    main()
