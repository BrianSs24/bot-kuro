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

# =========================
# BOT
# =========================

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)

# =========================
# BASE DE DATOS POSTGRESQL
# =========================

conexion = psycopg2.connect(DATABASE_URL)
cursor = conexion.cursor()

# =========================
# TABLAS
# =========================

cursor.execute("""
CREATE TABLE IF NOT EXISTS puntos_kuro (
    usuario TEXT PRIMARY KEY,
    puntos INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS puntos_tna (
    usuario TEXT PRIMARY KEY,
    puntos INTEGER
)
""")

conexion.commit()

# =========================
# BOT LISTO
# =========================

@bot.event
async def on_ready():
    print(f"✅ Bot conectado como {bot.user}")

# =========================
# DETECTAR INFORMES
# =========================

@bot.event
async def on_message(message):

    # SOLO mensajes del bot MineLatino
    if message.author.name == "Ultimate Clans V7":

        # =========================
        # LEER MENSAJE Y EMBEDS
        # =========================

        contenido = ""

        # Mensaje normal
        if message.content:
            contenido += message.content

        # Embeds de MineLatino
        if message.embeds:

            for embed in message.embeds:

                if embed.description:
                    contenido += " " + embed.description

        # =========================
        # REGEX
        # =========================

        patron = r"(.*?) ha conseguido ([\d\.]+) puntos para este clan"

        resultado = re.search(patron, contenido)

        if resultado:

            usuario = resultado.group(1).strip()

            puntos = resultado.group(2)
            puntos = puntos.replace(".", "")
            puntos = int(puntos)

            # =====================================================
            # ======================= KURO =========================
            # =====================================================

            if message.channel.name == CANAL_KURO:

                cursor.execute(
                    "SELECT puntos FROM puntos_kuro WHERE usuario = %s",
                    (usuario,)
                )

                fila = cursor.fetchone()

                if fila:

                    nuevos_puntos = fila[0] + puntos

                    cursor.execute(
                        "UPDATE puntos_kuro SET puntos = %s WHERE usuario = %s",
                        (nuevos_puntos, usuario)
                    )

                else:

                    cursor.execute(
                        "INSERT INTO puntos_kuro(usuario, puntos) VALUES(%s, %s)",
                        (usuario, puntos)
                    )

                conexion.commit()

                await message.channel.send(
                    f"✅ {usuario} sumó {puntos:,} puntos al registro KURO."
                )

            # =====================================================
            # ======================== TNA =========================
            # =====================================================

            elif message.channel.name == CANAL_TNA:

                cursor.execute(
                    "SELECT puntos FROM puntos_tna WHERE usuario = %s",
                    (usuario,)
                )

                fila = cursor.fetchone()

                if fila:

                    nuevos_puntos = fila[0] + puntos

                    cursor.execute(
                        "UPDATE puntos_tna SET puntos = %s WHERE usuario = %s",
                        (nuevos_puntos, usuario)
                    )

                else:

                    cursor.execute(
                        "INSERT INTO puntos_tna(usuario, puntos) VALUES(%s, %s)",
                        (usuario, puntos)
                    )

                conexion.commit()

                await message.channel.send(
                    f"✅ {usuario} sumó {puntos:,} puntos al registro TNA."
                )

    # IMPORTANTE PARA COMANDOS
    await bot.process_commands(message)

# =========================================================
# ====================== COMANDOS KURO ====================
# =========================================================

@bot.command()
async def topkuro(ctx):

    cursor.execute(
        "SELECT usuario, puntos FROM puntos_kuro ORDER BY puntos DESC"
    )

    datos = cursor.fetchall()

    if not datos:
        await ctx.send("No hay puntos registrados en KURO.")
        return

    mensaje = "🏆 Ranking KURO 🏆\n\n"

    posicion = 1

    for usuario, puntos in datos:

        mensaje += f"{posicion}. {usuario} → {puntos:,} puntos\n"

        posicion += 1

    await ctx.send(f"```{mensaje}```")

# =========================
# PUNTOS KURO
# =========================

@bot.command()
async def puntoskuro(ctx, usuario):

    cursor.execute(
        "SELECT puntos FROM puntos_kuro WHERE usuario = %s",
        (usuario,)
    )

    resultado = cursor.fetchone()

    if resultado:

        await ctx.send(
            f"📊 {usuario} tiene {resultado[0]:,} puntos en KURO."
        )

    else:

        await ctx.send(
            "Ese usuario no existe en KURO."
        )

# =========================
# RESET KURO
# =========================

@bot.command()
@commands.has_permissions(administrator=True)
async def resetkuro(ctx):

    cursor.execute("DELETE FROM puntos_kuro")

    conexion.commit()

    await ctx.send(
        "♻️ La tabla KURO fue reiniciada."
    )

# =========================
# BORRAR USUARIO KURO
# =========================

@bot.command()
@commands.has_permissions(administrator=True)
async def borrarusuariokuro(ctx, usuario):

    cursor.execute(
        "DELETE FROM puntos_kuro WHERE usuario = %s",
        (usuario,)
    )

    conexion.commit()

    await ctx.send(
        f"🗑️ Usuario {usuario} eliminado de KURO."
    )

# =========================================================
# ====================== COMANDOS TNA =====================
# =========================================================

@bot.command()
async def toptna(ctx):

    cursor.execute(
        "SELECT usuario, puntos FROM puntos_tna ORDER BY puntos DESC"
    )

    datos = cursor.fetchall()

    if not datos:
        await ctx.send("No hay puntos registrados en TNA.")
        return

    mensaje = "🏆 Ranking TNA 🏆\n\n"

    posicion = 1

    for usuario, puntos in datos:

        mensaje += f"{posicion}. {usuario} → {puntos:,} puntos\n"

        posicion += 1

    await ctx.send(f"```{mensaje}```")

# =========================
# PUNTOS TNA
# =========================

@bot.command()
async def puntostna(ctx, usuario):

    cursor.execute(
        "SELECT puntos FROM puntos_tna WHERE usuario = %s",
        (usuario,)
    )

    resultado = cursor.fetchone()

    if resultado:

        await ctx.send(
            f"📊 {usuario} tiene {resultado[0]:,} puntos en TNA."
        )

    else:

        await ctx.send(
            "Ese usuario no existe en TNA."
        )

# =========================
# RESET TNA
# =========================

@bot.command()
@commands.has_permissions(administrator=True)
async def resettna(ctx):

    cursor.execute("DELETE FROM puntos_tna")

    conexion.commit()

    await ctx.send(
        "♻️ La tabla TNA fue reiniciada."
    )

# =========================
# BORRAR USUARIO TNA
# =========================

@bot.command()
@commands.has_permissions(administrator=True)
async def borrarusuariotna(ctx, usuario):

    cursor.execute(
        "DELETE FROM puntos_tna WHERE usuario = %s",
        (usuario,)
    )

    conexion.commit()

    await ctx.send(
        f"🗑️ Usuario {usuario} eliminado de TNA."
    )

# =========================
# COMANDO TEST
# =========================

@bot.command()
async def ping(ctx):
    await ctx.send("pong")

# =========================
# EJECUTAR BOT
# =========================

bot.run(TOKEN)