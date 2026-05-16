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

CANAL_KURO_ID = 1331359760414539791  # <-- tu ID real

# =========================
# INTENTS
# =========================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# =========================
# DATABASE
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
# ON MESSAGE (ARREGLADO)
# =========================

@bot.event
async def on_message(message):

    # ❌ ignorar bots
    if message.author.bot:
        await bot.process_commands(message)
        return

    # =========================
    # SOLO KURO
    # =========================

    if message.channel.id == CANAL_KURO_ID:

        contenido = message.content or ""

        if message.embeds:
            for embed in message.embeds:
                if embed.description:
                    contenido += " " + embed.description
                if embed.fields:
                    for field in embed.fields:
                        contenido += f" {field.name} {field.value}"

        print("\n====================")
        print("📩 MENSAJE KURO")

        # =========================
        # EXTRAER BLOQUE
        # =========================

        match_par = re.search(r"\((.*?)\)", contenido)
        if match_par:

            bloque = match_par.group(1)

            match = re.search(
                r"([\w\d_]+)\s+ha\s+conseguido\s+([\d\.,]+)",
                bloque
            )

            if match:

                usuario = match.group(1).lower()
                puntos = int(match.group(2).replace(".", "").replace(",", ""))

                try:
                    cursor.execute("""
                        INSERT INTO puntos_kuro (usuario, puntos)
                        VALUES (%s, %s)
                        ON CONFLICT (usuario)
                        DO UPDATE SET puntos = puntos_kuro.puntos + EXCLUDED.puntos
                    """, (usuario, puntos))

                    conexion.commit()

                    await message.channel.send(
                        f"✅ {usuario} +{puntos:,} puntos KURO"
                    )

                except Exception as e:
                    print("❌ ERROR BD:", e)

    # 🔥 IMPORTANTE: SIEMPRE ejecutar comandos al final
    await bot.process_commands(message)

# =========================
# COMANDOS
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

    if not data:
        return await ctx.send("No hay datos.")

    msg = "🏆 KURO TOP 🏆\n\n"

    for i, (u, p) in enumerate(data, 1):
        msg += f"{i}. {u} → {p:,}\n"

    await ctx.send(f"```{msg}```")

# =========================
# RUN
# =========================

bot.run(TOKEN)