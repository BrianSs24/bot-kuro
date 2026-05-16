import discord
from discord.ext import commands
import psycopg2
import re
import os

# =========================
# VARIABLES
# =========================

TOKEN = os.getenv("TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

CANAL_KURO = "registro-kuro"
CANAL_TNA = "registro-tna"

# =========================
# INTENTS
# =========================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# =========================
# BASE DE DATOS
# =========================

conexion = psycopg2.connect(DATABASE_URL, sslmode="require")
cursor = conexion.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS puntos_kuro (
    usuario TEXT PRIMARY KEY,
    puntos BIGINT DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS puntos_tna (
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
# ON MESSAGE
# =========================

@bot.event
async def on_message(message):

    if message.author.bot:
        await bot.process_commands(message)
        return

    # =========================
    # CONSTRUIR CONTENIDO
    # =========================

    contenido = message.content or ""

    if message.embeds:
        for embed in message.embeds:

            if embed.description:
                contenido += " " + embed.description

            if embed.fields:
                for field in embed.fields:
                    contenido += f" {field.name} {field.value}"

    contenido = contenido.strip()

    print("\n====================")
    print("📩 MENSAJE:", contenido)
    print("📌 CANAL:", message.channel.name)

    # =========================
    # REGEX
    # =========================

    patron = r"([\w\W]+?)\s+ha\s+conseguido\s+([\d\.,]+)\s+puntos"
    resultado = re.search(patron, contenido, re.IGNORECASE)

    if not resultado:
        print("❌ NO MATCH REGEX")
        await bot.process_commands(message)
        return

    print("✔ REGEX OK")

    usuario = resultado.group(1).strip().lower()
    puntos = int(resultado.group(2).replace(".", "").replace(",", ""))

    print("👤 USUARIO:", usuario)
    print("⭐ PUNTOS:", puntos)

    # =========================
    # NORMALIZAR CANAL
    # =========================

    canal_actual = message.channel.name.strip().casefold()

    # =========================
    # KURO
    # =========================

    if canal_actual == CANAL_KURO.casefold():

        try:
            cursor.execute("""
                INSERT INTO puntos_kuro (usuario, puntos)
                VALUES (%s, %s)
                ON CONFLICT (usuario)
                DO UPDATE SET puntos = puntos_kuro.puntos + EXCLUDED.puntos
            """, (usuario, puntos))

            conexion.commit()

            print("💾 GUARDADO EN KURO OK")

            await message.channel.send(
                f"✅ {usuario} sumó {puntos:,} puntos en KURO."
            )

        except Exception as e:
            print("❌ ERROR KURO:", e)

    # =========================
    # TNA
    # =========================

    elif canal_actual == CANAL_TNA.casefold():

        try:
            cursor.execute("""
                INSERT INTO puntos_tna (usuario, puntos)
                VALUES (%s, %s)
                ON CONFLICT (usuario)
                DO UPDATE SET puntos = puntos_tna.puntos + EXCLUDED.puntos
            """, (usuario, puntos))

            conexion.commit()

            print("💾 GUARDADO EN TNA OK")

            await message.channel.send(
                f"✅ {usuario} sumó {puntos:,} puntos en TNA."
            )

        except Exception as e:
            print("❌ ERROR TNA:", e)

    else:
        print("⚠ CANAL NO RECONOCIDO")

    await bot.process_commands(message)

# =========================
# COMANDO TEST
# =========================

@bot.command()
async def ping(ctx):
    await ctx.send("pong")

# =========================
# RUN BOT
# =========================

bot.run(TOKEN)