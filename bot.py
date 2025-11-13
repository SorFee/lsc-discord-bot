import re
import os
import discord
from discord.ext import commands

# 👇 NOVÉ IMPORTY PRO WEBSERVER
from flask import Flask
from threading import Thread

# ================== KONFIGURACE ==================

TOKEN = os.getenv("DISCORD_TOKEN")  # vezme token z tajné proměnné v Repl.it

LOG_CHANNEL_ID = 1423698656200102042        # Captain Hook log kanál (tuning logy)
CONTROL_CHANNEL_ID = 1438474181170692116    # kanál kam bot pošle varování (zatím ho tady ani nepotřebujeme)

# roomka mechanika -> char ID mechanika
MECH_CHANNELS = {
    1438476562948296766: "79e1f496732d0cd479e80d8f20f348744a873a60",  # Mechanik 1 (už máš) SorFee moje roomka

    1422292003827355729: "53b0ab1316aa51cca52f79c6f16f0f271b226de2",   # lango_s
    1430287396460691649: "97fdef5a5c5404a6534e3ad69ae238e6ceb8631c",   # grunwick
    1433225117634269235: "7943e0159fd005ffa5f3067a22d059412d9411c3",   # 6m1kr06
    1434912107006136494: "84d6ec5f5e978c61786af02fc23810536067ce6e",   # Svoryyy
    1433225086411735311: "cb1d61ca99811b2d716624d72b1bc80cc0e291f1",   # @nxk
    1434474783768187001: "50d65834561632964c723cfa71c3389e5a88fb45",   # sh1mzz
    1434954803577884726: "4a91f65e0ce483525dc51d0bd2eba36f6b7de739",   # ice
    1434948555868737546: "b7e8dc741ae42cb4bda0b6dc028b5acd4f7ffe6b",   # tadeas
    1435289465563385896: "20d6b0835c720ade60584ad2fb6a472f8589eeb7",   # ッČajíček_czッ

    1436798379374936094: "77eed26d4053846504f163601dcc38e65dcc8474",  # peepiqq
    1432016180171898881: "f1973a78d80c52ca260349fad94ad965271c3910",  # KryoNix
    1435284157768138884: "c6725cf14bf3eb2dd66b2238c8cec17c2807ce75",  # Alexík
    1435292998593286296: "21ddd4c592c44d4b82b3e002318c8cf57bff5047",  # tezuuu
    1434561873994317969: "8e8c6d83af28c6d906b49bf883ff1eab808501bf",  # Trapy
    1434594507168682158: "f190bf642c4a35d1e4e910d9943dec4ca73cec8e",  # Petexino
    1430229108255752203: "b7d0c7fad38b420898b966fd2910711c92ca61e1",  # bimbo
    1429084399076642937: "19e9441ded536ed3bb4f960d4bb147ed3f6cda56",  # mikulaš
    1434166070242967634: "5b3f811c46a0e22d9e6287f9744c51164db9e905",  # zephyr
}

# char ID -> roomka mechanika (obrácené mapování pro auto-zápis z logu)
CHAR_TO_CHANNEL = {char_id: chan_id for chan_id, char_id in MECH_CHANNELS.items()}

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# slovníky: char_id -> částka
logs_per_char: dict[str, int] = {}       # součet z logu (jen tuningy)
reported_per_char: dict[str, int] = {}   # necháme pro kompatibilitu se stavchar/transakce

# ================== POMOCNÉ FUNKCE ==================

def parse_price_from_log(text: str) -> int | None:
    """
    Player **SorFee** **[34]** paid **$750** for tuning...
    """
    m = re.search(r"paid.*?\$\s*([\d,]+)", text)
    if m:
        try:
            return int(m.group(1).replace(",", ""))
        except ValueError:
            return None
    return None

def parse_charid_from_log(full_text: str) -> str | None:
    m = re.search(r"char\d*:\s*([0-9a-fA-F]+)", full_text)
    if m:
        return m.group(1)
    return None

# ================== EVENTY ==================

@bot.event
async def on_ready():
    print(f"Přihlášen jako {bot.user} (ID: {bot.user.id})")

@bot.event
async def on_message(message: discord.Message):
    global logs_per_char, reported_per_char

    # ignoruj zprávy od bota
    if message.author == bot.user:
        return

    # 1) LOG KANÁL – Captain Hook
    if message.channel.id == LOG_CHANNEL_ID and message.embeds:
        embed = message.embeds[0]

        desc = embed.description or ""
        full_text = desc
        if embed.footer and embed.footer.text:
            full_text += "\n" + embed.footer.text

        # DEBUG
        print("========== NOVÝ LOG ==========")
        print(full_text)
        print("================================")

        # IGNORACE čisté opravy / mytí (pokud v logu není žádný skutečný tuning)
        if "Tuning List:" in full_text:

            # Najdeme všechny řádky obsahující částku
            tuning_items = [line for line in full_text.split("\n") if "$" in line]

            # Pokud KAŽDÁ položka je pouze oprava nebo mytí → ignoruj
            if all(
                ("Opravit vozidlo" in item or "Umyt vozidlo" in item)
                for item in tuning_items
            ):
                print("[LOG] Ignorováno – jen oprava/mytí (žádný tuning).")
                return




        amount = parse_price_from_log(desc)
        char_id = parse_charid_from_log(full_text)

        if amount is not None and char_id is not None:
            # přičti do součtu pro daný char
            logs_per_char[char_id] = logs_per_char.get(char_id, 0) + amount
            print(f"[LOG] char {char_id} +{amount}, celkem {logs_per_char[char_id]}")

            # ⚙ AUTO-ZÁPIS do roomky mechanika
            mech_channel_id = CHAR_TO_CHANNEL.get(char_id)
            if mech_channel_id is not None:
                mech_channel = bot.get_channel(mech_channel_id)
                if mech_channel is not None:
                    await mech_channel.send(f"${amount}")

    # propusť příkazy (!say, !stavchar, !transakce)
    await bot.process_commands(message)

# ================== PŘÍKAZY ==================

@bot.command()
async def say(ctx, *, message: str):
    try:
        await ctx.message.delete()
    except discord.Forbidden:
        print("Nemám právo mazat zprávy.")
    except discord.HTTPException:
        print("Chyba při mazání zprávy.")
    await ctx.send(message)


@bot.command()
@commands.has_permissions(administrator=True)
async def stavchar(ctx, char_id: str):
    logged = logs_per_char.get(char_id, 0)
    reported = reported_per_char.get(char_id, 0)
    await ctx.send(
        f"📊 Stav pro char `{char_id}`:\n"
        f"- Z logu: **{logged}**\n"
        f"- Nahlášeno v roomce: **{reported}**\n"
        f"- Rozdíl: **{logged - reported}**"
    )


@bot.command()
@commands.has_permissions(administrator=True)
async def transakce(ctx, char_id: str = None):
    """
    Vypočítá celkový tuning pro char, spočítá 50 % a pošle TRANSAKCE blok.
    Po odeslání se částka vynuluje — reset období.
    """

    # 🧹 Smazat příkaz uživatele (!transakce)
    try:
        await ctx.message.delete()
    except:
        pass

    # Pokud není char_id, odvodíme ho podle místnosti
    if char_id is None:
        if ctx.channel.id in MECH_CHANNELS:
            char_id = MECH_CHANNELS[ctx.channel.id]
        else:
            await ctx.send("❌ Neznámý char – napiš buď v roomce mechanika, nebo použij `!transakce <char_id>`.")           
            return

    total = logs_per_char.get(char_id, 0)

    if total <= 0:
        await ctx.send(f"❌ Pro char `{char_id}` nemám v logu žádný nepřevedený tuning.")
        return

    payout = total // 2  # 50 %

    text = (
        "# :pushpin:  ***TRANSAKCE***\n\n"
        "||-----------------------------------------||\n\n"
        ":hourglass_flowing_sand: **Stav:** *ČEKÁ NA VYPLACENÍ :orange_circle:*\n"
        f":heavy_dollar_sign: **Částka:** *{total}*\n"
        f":money_with_wings: **Výplata (50 %):** *{payout}*\n\n"
        "||-----------------------------------------||"
    )

    await ctx.send(text)

    # 🔁 RESET po úspěšné transakci
    logs_per_char[char_id] = 0
    reported_per_char.pop(char_id, None)

    print(f"[RESET] Transakce pro {char_id}: total={total}, payout={payout} => vše vynulováno.")

# ================== MALÝ WEBSERVER PRO 24/7 ==================

app = Flask(__name__)

@app.route("/")
def home():
    return "LSC Service Bot is alive!"

def run_web():
    app.run(host="0.0.0.0", port=8080)

def keep_alive():
    t = Thread(target=run_web)
    t.start()

# ================== RUN ==================

if __name__ == "__main__":
    keep_alive()      # nastartuje webserver na pozadí
    bot.run(TOKEN)





