import asyncio
import csv
import re
from typing import Dict

import httpx
from bs4 import BeautifulSoup

BASE_URL = "https://bhubharati.telangana.gov.in"

# ====== UPDATE THIS WHEN COOKIE EXPIRES ======
JSESSIONID = "Xa0fz-ruigEdhouy4rMYzswrJcjkbzj_izrB9cC9.dharani-app-prod01"
# =============================================

COMMON_HEADERS = {
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    "Content-type": "application/x-www-form-urlencoded",
    "Referer": "https://bhubharati.telangana.gov.in/knowLandStatus",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
    "sec-ch-ua": '"Chromium";v="142", "Google Chrome";v="142", "Not_A Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}

COMMON_COOKIES = {
    "org.springframework.web.servlet.i18n.CookieLocaleResolver.LOCALE": "en",
    "JSESSIONID": JSESSIONID,
}


def extract_options(html_text: str) -> Dict[str, str]:
    """Extract <option value="...">text</option> pairs from any HTML snippet."""
    options: Dict[str, str] = {}

    # Try BeautifulSoup first
    try:
        soup = BeautifulSoup(html_text, "html.parser")
        for opt in soup.find_all("option"):
            value = (opt.get("value") or "").strip()
            text = (opt.text or "").strip()
            if value or text:
                options[value] = text
        if options:
            return options
    except Exception:
        pass

    # Fallback regex
    pattern = r'<option\s+value="([^"]*)"\s*>([^<]*)</option>'
    for value, text in re.findall(pattern, html_text):
        value = value.strip()
        text = text.strip()
        if value or text:
            options[value] = text

    return options


async def fetch_text(
    client: httpx.AsyncClient, url: str, label: str, params: Dict = None
) -> str | None:
    """Generic GET with logging; returns text or None."""
    try:
        resp = await client.get(url, params=params, timeout=30.0)
    except Exception as e:
        print(f"[ERROR] {label}: request failed → {e}")
        return None

    if resp.status_code != 200:
        print(f"[ERROR] {label}: HTTP {resp.status_code}")
        return None

    text = resp.text.strip()
    if not text:
        print(f"[WARN] {label}: empty body (status 200)")
        return None

    return text


# ---------------- DISTRICTS FROM /knowLandStatus ----------------- #
async def get_districts(client: httpx.AsyncClient) -> Dict[int, str]:
    """
    GET /knowLandStatus (your curl) and parse the district dropdown.

    curl "https://bhubharati.telangana.gov.in/knowLandStatus" ...
    """
    url = f"{BASE_URL}/knowLandStatus"
    label = "districts"

    # Headers as per your curl, merged with client defaults
    page_headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Cache-Control": "max-age=0",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    }

    try:
        resp = await client.get(url, headers=page_headers, timeout=30.0)
    except Exception as e:
        print(f"[ERROR] {label}: request failed → {e}")
        return {}

    if resp.status_code != 200:
        print(f"[ERROR] {label}: HTTP {resp.status_code}")
        return {}

    html = resp.text
    soup = BeautifulSoup(html, "html.parser")

    # Try to find the specific <select> for district
    sel = soup.find(
        lambda tag: (
            tag.name == "select"
            and (
                "district" in tag.get("id", "").lower()
                or "district" in tag.get("name", "").lower()
            )
        )
    )
    if not sel:
        # Fallback: first select; worst case we’ll filter by numeric values
        sel = soup.find("select")

    if not sel:
        print("[ERROR] No <select> found on knowLandStatus page")
        return {}

    districts: Dict[int, str] = {}
    for opt in sel.find_all("option"):
        val = (opt.get("value") or "").strip()
        text = (opt.text or "").strip()
        if not val:
            continue
        if "select" in text.lower():
            # e.g., "Please Select District"
            continue
        # keep only numeric IDs → reduces noise from other dropdowns
        if not val.isdigit():
            continue
        districts[int(val)] = text

    if not districts:
        print("[WARN] Could not parse any districts from page")
    else:
        print(f"[OK] Found {len(districts)} districts from page")

    return districts


# ---------------- MANDAL / VILLAGE / SURVEY / KHATA ---------------- #

async def get_mandals(client: httpx.AsyncClient, district_id: int) -> Dict[str, str]:
    url = f"{BASE_URL}/getMandalFromDivisionCitizenPortal"
    label = f"mandals[district={district_id}]"
    html = await fetch_text(client, url, label, params={"district": district_id})
    if not html:
        return {}

    options = extract_options(html)
    cleaned = {
        code: name
        for code, name in options.items()
        if code and code not in ("0", "Please Select")
    }

    if not cleaned:
        print(f"[INFO] No mandals parsed for district={district_id}")
    else:
        print(f"[OK] {len(cleaned)} mandals for district={district_id}")

    return cleaned


async def get_villages(client: httpx.AsyncClient, mandal_id: int) -> Dict[str, str]:
    url = f"{BASE_URL}/getVillageFromMandalCitizenPortal"
    label = f"villages[mandal={mandal_id}]"
    html = await fetch_text(client, url, label, params={"mandalId": mandal_id})
    if not html:
        return {}

    options = extract_options(html)
    cleaned = {
        code: name
        for code, name in options.items()
        if code and code not in ("0", "Please Select")
    }

    if not cleaned:
        print(f"[INFO] No villages parsed for mandal={mandal_id}")
    else:
        print(f"[OK] {len(cleaned)} villages for mandal={mandal_id}")

    return cleaned


async def get_surveys(client: httpx.AsyncClient, village_id: int) -> Dict[str, str]:
    url = f"{BASE_URL}/getSurveyCitizen"
    label = f"surveys[village={village_id}]"
    html = await fetch_text(
        client, url, label, params={"villId": village_id, "flag": "survey"}
    )
    if not html:
        return {}

    options = extract_options(html)
    cleaned = {
        code: name
        for code, name in options.items()
        if code and code.lower() != "surveynumber" and code not in ("0", "Please Select")
    }

    if not cleaned:
        print(f"[INFO] No surveys parsed for village={village_id}")
    else:
        print(f"[OK] {len(cleaned)} surveys for village={village_id}")

    return cleaned


async def get_khatas(
    client: httpx.AsyncClient, village_id: int, survey_no: str
) -> Dict[str, str]:
    url = f"{BASE_URL}/getKhataNoCitizen"
    label = f"khatas[village={village_id}, survey={survey_no}]"
    html = await fetch_text(
        client,
        url,
        label,
        params={"villId": village_id, "flag": "khatanos", "surveyNo": survey_no},
    )
    if not html:
        return {}

    options = extract_options(html)
    cleaned = {
        code: name
        for code, name in options.items()
        if code and code not in ("0", "Please Select")
    }

    if not cleaned:
        print(f"[INFO] No khatas parsed for village={village_id}, survey={survey_no}")
    else:
        print(
            f"[OK] {len(cleaned)} khatas for village={village_id}, survey={survey_no}"
        )

    return cleaned


# ---------------- MAIN ---------------- #

async def main():
    mandal_csv = "Tmandal_tel.csv"
    village_csv = "Tvillage_tel.csv"
    survey_csv = "Tsurvey_tel.csv"
    khata_csv = "Tkhata_tel.csv"
    districts_csv = "Tdistrict_tel.csv"

    # async context only for the HTTP client
    async with httpx.AsyncClient(
        headers=COMMON_HEADERS, cookies=COMMON_COOKIES
    ) as client:

        # normal sync context for files
        with (
            open(districts_csv, "w", newline="", encoding="utf-8") as districts_f,
            open(mandal_csv, "w", newline="", encoding="utf-8") as mandal_f,
            open(village_csv, "w", newline="", encoding="utf-8") as village_f,
            open(survey_csv, "w", newline="", encoding="utf-8") as survey_f,
            open(khata_csv, "w", newline="", encoding="utf-8") as khata_f,
        ):

            district_writer = csv.writer(districts_f)
            district_writer.writerow(["district_id", "district_name"])

            mandal_writer = csv.writer(mandal_f)
            mandal_writer.writerow(["district_id", "mandal_id", "mandal_name"])

            village_writer = csv.writer(village_f)
            village_writer.writerow(["mandal_id", "village_id", "village_name"])

            survey_writer = csv.writer(survey_f)
            survey_writer.writerow(["village_id", "survey_no", "label"])

            khata_writer = csv.writer(khata_f)
            khata_writer.writerow(["village_id", "survey_no", "khata_id", "khata_label"])

            # 1) Get district list from /knowLandStatus
            districts = await get_districts(client)
            if not districts:
                print("[FATAL] No districts found – check JSESSIONID / page structure")
                return

            # 2) Loop districts → mandals → villages → surveys → khatas
            for dist_id, dist_name in districts.items():
                print(f"\n=== District: {dist_name} ({dist_id}) ===")
                mandals = await get_mandals(client, dist_id)
                if not mandals:
                    print(f"[WARN] No mandals for district={dist_id}")
                    continue

                for mandal_id_str, mandal_name in mandals.items():
                    try:
                        mandal_id = int(mandal_id_str)
                    except ValueError:
                        print(f"[SKIP] invalid mandal_id: {mandal_id_str!r}")
                        continue

                    mandal_writer.writerow([dist_id, mandal_id, mandal_name])
                    print(f"  Mandal: {mandal_name} ({mandal_id})")

                    villages = await get_villages(client, mandal_id)
                    if not villages:
                        print(
                            f"  [WARN] No villages for mandal={mandal_id} ({mandal_name})"
                        )
                        continue

                    for village_id_str, village_name in villages.items():
                        try:
                            village_id = int(village_id_str)
                        except ValueError:
                            print(f"  [SKIP] invalid village_id: {village_id_str!r}")
                            continue

                        village_writer.writerow([mandal_id, village_id, village_name])
                        print(f"    Village: {village_name} ({village_id})")

                        surveys = await get_surveys(client, village_id)
                        if not surveys:
                            print(
                                f"    [WARN] No surveys for village={village_id} ({village_name})"
                            )
                            continue

                        for survey_no, survey_label in surveys.items():
                            survey_writer.writerow(
                                [village_id, survey_no, survey_label]
                            )

                            khatas = await get_khatas(client, village_id, survey_no)
                            if not khatas:
                                print(
                                    f"    [WARN] No khatas for village={village_id}, survey={survey_no}"
                                )
                                continue

                                # if you only want at least to log, you already did above

                            for khata_id, khata_label in khatas.items():
                                khata_writer.writerow(
                                    [village_id, survey_no, khata_id, khata_label]
                                )

            print("\nDone.")
            print(f"Mandals  → {mandal_csv}")
            print(f"Villages → {village_csv}")
            print(f"Surveys  → {survey_csv}")
            print(f"Khatas   → {khata_csv}")

if __name__ == "__main__":
    asyncio.run(main())
