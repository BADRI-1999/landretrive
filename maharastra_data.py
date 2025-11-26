import asyncio
import aiohttp
import csv
from bs4 import BeautifulSoup

BASE_URL = "https://bhulekh.mahabhumi.gov.in/"

HEADERS = {
    "Accept": "*/*",
    "Accept-Language": "en-IN",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "DNT": "1",
    "Origin": BASE_URL,
    "Referer": BASE_URL,
    "X-Requested-With": "XMLHttpRequest",
    "User-Agent": "Mozilla/5.0",
}


# ------------------ HTML / STATE HELPERS ------------------ #

def extract_options(html_text: str, select_id: str) -> dict:
    """
    Extract <option value> from any <select> whose id contains select_id.
    Works on both full HTML and ASP.NET UpdatePanel snippets.
    """
    soup = BeautifulSoup(html_text, "html.parser")

    sel = soup.find("select", id=lambda x: x and select_id in x)
    if not sel:  # fallback by name
        sel = soup.find("select", attrs={"name": lambda x: x and select_id in x})

    options = {}
    if sel:
        for opt in sel.find_all("option"):
            key = (opt.get("value") or "").strip()
            val = (opt.text or "").strip()
            if key not in ["", "--निवडा--"]:
                options[key] = val
    return options


def parse_hidden_fields_from_html(html_text: str) -> dict:
    """
    Parse all <input type="hidden" name="..." value="..."> fields from HTML.
    Used for __VIEWSTATE, __EVENTVALIDATION, etc.
    """
    soup = BeautifulSoup(html_text, "html.parser")
    hidden = {}
    for inp in soup.find_all("input", type="hidden"):
        name = inp.get("name")
        if not name:
            continue
        hidden[name] = inp.get("value", "")
    return hidden


def parse_hidden_fields_from_async_postback(text: str) -> dict:
    """
    ASP.NET ScriptManager async postbacks encode hidden fields in a pipe-delimited format:
      ...|hiddenField|__VIEWSTATE|<value>|hiddenField|__EVENTVALIDATION|<value>|...

    This scans that format and extracts those pairs.
    """
    fields = {}
    if "hiddenField" not in text:
        return fields

    parts = text.split("|")
    # Look for triples: ["hiddenField", name, value]
    for i in range(len(parts) - 2):
        if parts[i] == "hiddenField":
            name = parts[i + 1]
            value = parts[i + 2]
            fields[name] = value
    return fields


def update_form_state(form_state: dict, text: str) -> dict:
    """
    Update our stored form_state with any new hidden fields from the response.
    Works both for full-page HTML and async-postback responses.
    """
    # From HTML snippet / full page (if present)
    html_hidden = parse_hidden_fields_from_html(text)
    if html_hidden:
        form_state.update(html_hidden)

    # From ASP.NET async postback pipe format
    async_hidden = parse_hidden_fields_from_async_postback(text)
    if async_hidden:
        form_state.update(async_hidden)

    return form_state


# ------------------ NETWORK HELPERS ------------------ #

async def post(session: aiohttp.ClientSession, url: str, data: dict, retries: int = 3) -> str:
    """
    Resilient POST with retry/backoff.
    """
    for attempt in range(1, retries + 1):
        try:
            async with session.post(url, data=data, timeout=20) as resp:
                txt = await resp.text()
                if resp.status == 200:
                    return txt
                print(f"⚠ HTTP {resp.status}. Retrying {attempt}/{retries}...")
        except Exception as e:
            print(f"⚠ Error {e}. Retry {attempt}/{retries}...")
        await asyncio.sleep(attempt)  # simple backoff: 1s, 2s, 3s...

    return ""


# ------------------ SCRAPING STEPS ------------------ #

async def fetch_districts(session: aiohttp.ClientSession):
    """
    Initial GET: get full page, parse districts and initial form_state (__VIEWSTATE, etc.).
    """
    async with session.get(BASE_URL) as resp:
        html = await resp.text()

    districts = extract_options(html, "ddlMainDist")
    form_state = parse_hidden_fields_from_html(html)

    print(f"✔ Found {len(districts)} districts")
    return districts, form_state


async def fetch_mandals(session: aiohttp.ClientSession, dist_code: str, form_state: dict):
    """
    Fetch mandals for a given district by simulating ASP.NET dropdown postback.
    """
    # Start from current hidden state (VIEWSTATE, EVENTVALIDATION, etc.)
    data = dict(form_state)

    # Event: main district dropdown changed
    data.update({
        "ctl00$ContentPlaceHolder1$ScriptManager1":
            "ctl00$ContentPlaceHolder1$UpdatePanel1|ctl00$ContentPlaceHolder1$ddlMainDist",
        "__EVENTTARGET": "ctl00$ContentPlaceHolder1$ddlMainDist",
        "__EVENTARGUMENT": "",
        "__LASTFOCUS": "",

        # Dist selection
        "ctl00$ContentPlaceHolder1$ddlMainDist": str(dist_code),

        # Search settings (from your original payload)
        "ctl00$ContentPlaceHolder1$rbtnULPIN": "Know-no",
        "ctl00$ContentPlaceHolder1$rbtnSelectType": "SelectSatbara",
        "ctl00$ContentPlaceHolder1$rbtnSearchType": "17",
        "ctl00$ContentPlaceHolder1$ddlSelectSearchType": "--निवडा--",

        "__ASYNCPOST": "true",
    })

    html = await post(session, BASE_URL, data)
    mandals = extract_options(html, "ddlTalForAll")

    if not mandals:
        print(f"❌ No mandals for district {dist_code}")

    # Update VIEWSTATE, EVENTVALIDATION, etc. for next requests
    form_state = update_form_state(form_state, html)

    return mandals, form_state


async def fetch_villages(
    session: aiohttp.ClientSession,
    dist_code: str,
    mandal_code: str,
    form_state: dict,
):
    """
    Fetch villages for a mandal via ASP.NET dropdown postback.
    """
    # Be gentle with server (your original code had 10s sleep)
    await asyncio.sleep(10)

    data = dict(form_state)

    data.update({
        "ctl00$ContentPlaceHolder1$ScriptManager1":
            "ctl00$ContentPlaceHolder1$UpdatePanel1|ctl00$ContentPlaceHolder1$ddlTalForAll",

        "ctl00$ContentPlaceHolder1$rbtnULPIN": "Know-no",
        "ctl00$ContentPlaceHolder1$rbtnSelectType": "SelectSatbara",

        # District + mandal
        "ctl00$ContentPlaceHolder1$ddlMainDist": str(dist_code),
        "ctl00$ContentPlaceHolder1$ddlTalForAll": str(mandal_code),

        # Search mode you used for villages
        "ctl00$ContentPlaceHolder1$rbtnSearchType": "17",
        "ctl00$ContentPlaceHolder1$ddlSelectSearchType": "2",

        "__EVENTTARGET": "ctl00$ContentPlaceHolder1$ddlTalForAll",
        "__EVENTARGUMENT": "",
        "__LASTFOCUS": "",
        "__ASYNCPOST": "true",
    })

    html = await post(session, BASE_URL, data)
    villages = extract_options(html, "ddlVillForAll")

    if not villages:
        print(f"❌ No villages for mandal {mandal_code} under district {dist_code}")

    form_state = update_form_state(form_state, html)

    return villages, form_state


# ------------------ MAIN ORCHESTRATION ------------------ #

async def main():
    # Let aiohttp manage session cookies (no hard-coded ASP.NET_SessionId)
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        # ---------- Fetch Districts + initial state ----------
        districts, form_state = await fetch_districts(session)

        # CSV writers (context managers auto-close)
        with (
            open("district.csv", "w", newline="", encoding="utf-8") as dist_f,
            open("mandal.csv", "w", newline="", encoding="utf-8") as mandal_f,
            open("village.csv", "w", newline="", encoding="utf-8") as village_f,
        ):
            dist_writer = csv.writer(dist_f)
            mandal_writer = csv.writer(mandal_f)
            village_writer = csv.writer(village_f)

            dist_writer.writerow(["id", "value"])
            mandal_writer.writerow(["dist_id", "mandal_id", "value"])
            village_writer.writerow(["mandal_id", "village_id", "value"])

            # ---------- Loop over districts ----------
            for dist_code, dist_name in districts.items():
                print(f"\n============== District: {dist_name} ({dist_code}) ==============")
                dist_writer.writerow([dist_code, dist_name])

                mandals, form_state = await fetch_mandals(session, dist_code, form_state)

                # ---------- Loop over mandals ----------
                for mandal_code, mandal_name in mandals.items():
                    print(f"→ Mandal: {mandal_name} ({mandal_code})")
                    mandal_writer.writerow([dist_code, mandal_code, mandal_name])

                    villages, form_state = await fetch_villages(
                        session, dist_code, mandal_code, form_state
                    )

                    if not villages:
                        print(f"   ⚠ No villages found for {mandal_name}")
                    else:
                        for vill_code, vill_name in villages.items():
                            print(f"     • {vill_name}")
                            village_writer.writerow([mandal_code, vill_code, vill_name])

                    # Small extra throttle between mandals
                    await asyncio.sleep(0.2)

        print("\n✔ DONE! CSVs saved.")


if __name__ == "__main__":
    asyncio.run(main())
