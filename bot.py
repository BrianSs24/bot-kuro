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

CANAL_REGISTRO = "registro-kuro"

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
# CREAR TABLA
# =========================

cursor.execute("""
CREATE TABLE IF NOT EXISTS puntos (
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
    print(f"Bot conectado como {bot.user}")

# =========================
# DETECTAR INFORMES
# =========================

@bot.event
async def on_message(message):

    # Detectar SOLO mensajes del bot MineLatino
    if (
        message.author.name == "Ultimate Clans V7"
        and message.channel.name == CANAL_REGISTRO
    ):

        contenido = message.content

        patron = r"\((.*?) ha conseguido ([\d\.]+) puntos para este clan\)"

        resultado = re.search(patron, contenido)

        if resultado:

            usuario = resultado.group(1)

            puntos = resultado.group(2)
            puntos = puntos.replace(".", "")
            puntos = int(puntos)

            # Buscar usuario existente
            cursor.execute(
                "SELECT puntos FROM puntos WHERE usuario = %s",
                (usuario,)
            )

            fila = cursor.fetchone()

            # Si existe, sumar puntos
            if fila:

                nuevos_puntos = fila[0] + puntos

                cursor.execute(
                    "UPDATE puntos SET puntos = %s WHERE usuario = %s",
                    (nuevos_puntos, usuario)
                )

            # Si no existe, crearlo
            else:

                cursor.execute(
                    "INSERT INTO puntos(usuario, puntos) VALUES(%s, %s)",
                    (usuario, puntos)
                )

            conexion.commit()

            await message.channel.send(
                f"✅ {usuario} sumó {puntos:,} puntos al registro Kuro."
            )

    # IMPORTANTE:
    # Esto permite que funcionen los comandos
    await bot.process_commands(message)

# =========================
# RANKING
# =========================

@bot.command()
async def topkuro(ctx):

    cursor.execute(
        "SELECT usuario, puntos FROM puntos ORDER BY puntos DESC"
    )

    datos = cursor.fetchall()

    if not datos:
        await ctx.send("No hay puntos registrados.")
        return

    mensaje = "🏆 Ranking del Clan Kuro 🏆\n\n"

    posicion = 1

    for usuario, puntos in datos:

        mensaje += (
            f"{posicion}. {usuario} → {puntos:,} puntos\n"
        )

        posicion += 1

    await ctx.send(f"```{mensaje}```")

# =========================
# VER PUNTOS INDIVIDUALES
# =========================

@bot.command()
async def puntos(ctx, usuario):

    cursor.execute(
        "SELECT puntos FROM puntos WHERE usuario = %s",
        (usuario,)
    )

    resultado = cursor.fetchone()

    if resultado:

        await ctx.send(
            f"📊 {usuario} tiene {resultado[0]:,} puntos."
        )

    else:

        await ctx.send(
            "Ese usuario no existe."
        )

# =========================
# RESET COMPLETO
# =========================

@bot.command()
@commands.has_permissions(administrator=True)
async def resetkuro(ctx):

    cursor.execute("DELETE FROM puntos")

    conexion.commit()

    await ctx.send(
        "♻️ La tabla de puntos fue reiniciada correctamente."
    )

# =========================
# BORRAR USUARIO
# =========================

@bot.command()
@commands.has_permissions(administrator=True)
async def borrarusuario(ctx, usuario):

    cursor.execute(
        "DELETE FROM puntos WHERE usuario = %s",
        (usuario,)
    )

    conexion.commit()

    await ctx.send(
        f"🗑️ Usuario {usuario} eliminado."
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