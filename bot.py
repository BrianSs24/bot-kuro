import discord
from discord.ext import commands
import psycopg2
import re
import os

# =========================
# CONFIG
# =========================

TOKEN = os.getenv("TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

CANAL_KURO_ID = 1331359760414539791  # tu canal

# =========================
# INTENTS
# =========================

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# =========================
# DB
# =========================

conexion = psycopg2.connect(DATABASE_URL, sslmode="require")
cursor = conexion.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS puntos_kuro (
    usuario TEXT PRIMARY KEY,
    puntos BIGINT DEFAULT 0
)
""")

conexion.commit()

# =========================
# READY
# =========================

@bot.event
async def on_ready():
    print(f"✅ Bot conectado como {bot.user}")

# =========================
# EXTRACT FUNCTION
# =========================

def extraer_datos(texto):

    # =========================
    # FORMATO 1: con paréntesis
    # =========================
    match_parentesis = re.search(r"\((.*?)\)", texto)

    if match_parentesis:
        texto = match_parentesis.group(1)

    # =========================
    # FORMATO 2 o limpio
    # =========================
    match = re.search(
        r"([\w\d_]+)\s+ha\s+conseguido\s+([\d\.,]+)",
        texto,
        re.IGNORECASE
    )

    if not match:
        return None, None

    usuario = match.group(1).lower()
    puntos = int(match.group(2).replace(".", "").replace(",", ""))

    return usuario, puntos

# =========================
# MESSAGE
# =========================

@bot.event
async def on_message(message):

    # ❌ ignorar bots excepto MineLatino
    if message.author.bot and "MineLatino" not in message.author.name:
        return

    # SOLO canal KURO
    if message.channel.id != CANAL_KURO_ID:
        await bot.process_commands(message)
        return

    # =========================
    # CONSTRUIR MENSAJE
    # =========================

    contenido = message.content or ""

    for embed in message.embeds:
        if embed.description:
            contenido += " " + embed.description

    print("\n====================")
    print("📩 MENSAJE DETECTADO")
    print("CONTENIDO:", contenido)

    # =========================
    # EXTRAER DATOS
    # =========================

    usuario, puntos = extraer_datos(contenido)

    if not usuario:
        print("❌ NO SE PUDO EXTRAER DATA")
        await bot.process_commands(message)
        return

    print("✔ USUARIO:", usuario)
    print("⭐ PUNTOS:", puntos)

    # =========================
    # GUARDAR
    # =========================

    try:
        cursor.execute("""
            INSERT INTO puntos_kuro (usuario, puntos)
            VALUES (%s, %s)
            ON CONFLICT (usuario)
            DO UPDATE SET puntos = puntos_kuro.puntos + EXCLUDED.puntos
        """, (usuario, puntos))

        conexion.commit()

        print("💾 GUARDADO OK")

        await message.channel.send(
            f"✅ {usuario} +{puntos:,} puntos KURO"
        )

    except Exception as e:
        print("❌ ERROR BD:", e)

    await bot.process_commands(message)

# =========================
# COMMANDS
# =========================

@bot.command()
async def ping(ctx):
    await ctx.send("pong")

@bot.command()
@commands.has_permissions(administrator=True)
async def resetkuro(ctx):
    cursor.execute("DELETE FROM puntos_kuro")
    conexion.commit()
    await ctx.send("♻️ KURO reseteado.")

@bot.command()
async def topkuro(ctx):

    cursor.execute("""
        SELECT usuario, puntos
        FROM puntos_kuro
        ORDER BY puntos DESC
    """)

    data = cursor.fetchall()

    msg = "🏆 KURO TOP 🏆\n\n"

    for i, (u, p) in enumerate(data, 1):
        msg += f"{i}. {u} → {p:,}\n"

    await ctx.send(f"```{msg}```")

# =========================
# RUN
# =========================

bot.run(TOKEN)