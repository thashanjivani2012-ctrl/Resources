"""Clothing template showcase commands.

The image composition is intentionally kept separate from the command wiring so
the feature can also be reused by the standalone launcher in Resources Managament.
"""

from __future__ import annotations

import io
import json
import logging
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

import discord
from discord import app_commands

try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps
except ImportError:  # pragma: no cover - reported when the command is used
    Image = ImageDraw = ImageFont = ImageOps = None

SETTINGS_FILE = None
ASSETS_DIR = None
LOG = logging.getLogger("order-center.clothing-showcase")
MAX_IMAGE_BYTES = 12 * 1024 * 1024
LANDSCAPE_SIZE = (1600, 900)
PORTRAIT_SIZE = (1080, 1350)


def setup(bot, settings_file: Path, assets_dir: Path):
    global SETTINGS_FILE, ASSETS_DIR
    SETTINGS_FILE = settings_file
    ASSETS_DIR = assets_dir


def _read_settings() -> dict:
    if SETTINGS_FILE is None or not SETTINGS_FILE.exists():
        return {}
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        LOG.warning("Could not read showcase settings from %s.", SETTINGS_FILE)
        return {}
    return data if isinstance(data, dict) else {}


def _write_settings(data: dict):
    if SETTINGS_FILE is None:
        raise RuntimeError("Showcase settings are not configured.")
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _settings(guild: discord.Guild) -> dict:
    settings = _read_settings()
    return settings.setdefault(str(guild.id), {})


def _font(size: int, bold: bool = False):
    candidates = [
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


async def _attachment_bytes(attachment: discord.Attachment) -> bytes:
    if attachment.size > MAX_IMAGE_BYTES:
        raise ValueError(f"{attachment.filename} is larger than the {MAX_IMAGE_BYTES // 1024 // 1024} MB limit.")
    data = await attachment.read()
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError(f"{attachment.filename} is larger than the {MAX_IMAGE_BYTES // 1024 // 1024} MB limit.")
    return data


def _url_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "Resources-Managament-Showcase/1.0"})
    with urllib.request.urlopen(request, timeout=15) as response:
        data = response.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError("The background URL points to an image larger than 12 MB.")
    return data


def _open_image(data: bytes):
    if Image is None:
        raise RuntimeError("Pillow is not installed. Run `pip install -r requirements.txt`.")
    with Image.open(io.BytesIO(data)) as image:
        return image.convert("RGBA")


def _fit(image, box: tuple[int, int, int, int]):
    left, top, right, bottom = box
    fitted = ImageOps.contain(image, (right - left, bottom - top))
    return fitted, (left + (right - left - fitted.width) // 2, top + (bottom - top - fitted.height) // 2)


def _background_canvas(background, size: tuple[int, int]):
    width, height = size
    fitted, position = _fit(background, (0, 0, width, height))
    canvas = Image.new("RGBA", size, (245, 203, 218, 255))
    canvas.alpha_composite(fitted, position)
    return canvas


def _draw_image(draw, canvas, image, box):
    left, top, right, bottom = box
    draw.rounded_rectangle(box, radius=12, fill=(255, 255, 255, 225), outline="white", width=4)
    fitted, position = _fit(image, (left + 8, top + 8, right - 8, bottom - 8))
    canvas.alpha_composite(fitted, position)


def _compose_pairs(pairs: list[tuple], orientation: str, title: str, background):
    width, height = LANDSCAPE_SIZE if orientation == "landscape" else PORTRAIT_SIZE
    canvas = Image.new("RGBA", (width, height), (245, 203, 218, 255))
    if background is not None:
        canvas = _background_canvas(background, (width, height))
    draw = ImageDraw.Draw(canvas)
    title_font = _font(58 if orientation == "landscape" else 52, bold=True)
    title_text = title.strip()[:50] or "CLOTHING SHOWCASE"
    title_box = draw.textbbox((0, 0), title_text, font=title_font)
    title_x = (width - (title_box[2] - title_box[0])) // 2
    draw.text((title_x, 28), title_text, fill="white", font=title_font, stroke_width=2, stroke_fill=(90, 48, 65))

    margin = 52
    content_top = 118
    gap = 24
    if len(pairs) == 1:
        shirt, pants = pairs[0]
        if orientation == "landscape":
            box_width = (width - (2 * margin) - gap) // 2
            box = (margin, content_top, margin + box_width, height - margin)
            _draw_image(draw, canvas, shirt, box)
            box = (margin + box_width + gap, content_top, width - margin, height - margin)
            _draw_image(draw, canvas, pants, box)
        else:
            box_height = (height - content_top - margin - gap) // 2
            _draw_image(draw, canvas, shirt, (margin, content_top, width - margin, content_top + box_height))
            _draw_image(draw, canvas, pants, (margin, content_top + box_height + gap, width - margin, height - margin))
        return canvas

    if orientation == "landscape":
        columns = len(pairs)
        box_width = (width - (2 * margin) - gap * (columns - 1)) // columns
        box_height = (height - content_top - margin - gap) // 2
        for index, (shirt, pants) in enumerate(pairs):
            x = margin + index * (box_width + gap)
            _draw_image(draw, canvas, shirt, (x, content_top, x + box_width, content_top + box_height))
            _draw_image(draw, canvas, pants, (x, content_top + box_height + gap, x + box_width, height - margin))
    else:
        box_height = (height - content_top - margin - gap * (len(pairs) - 1)) // len(pairs)
        for index, (shirt, pants) in enumerate(pairs):
            y = content_top + index * (box_height + gap)
            half = (width - (2 * margin) - gap) // 2
            _draw_image(draw, canvas, shirt, (margin, y, margin + half, y + box_height))
            _draw_image(draw, canvas, pants, (margin + half + gap, y, width - margin, y + box_height))
    return canvas


async def _background_for(guild: discord.Guild, override: Optional[discord.Attachment]):
    if override is not None:
        return _open_image(await _attachment_bytes(override))
    saved = _settings(guild).get("background_path")
    if saved:
        path = Path(saved)
        if path.exists():
            return _open_image(path.read_bytes())
    return None


def _guild(interaction: discord.Interaction) -> discord.Guild:
    if interaction.guild is None:
        raise RuntimeError("This command can only be used inside a server.")
    return interaction.guild


clothing_group = app_commands.Group(name="clothing", description="Create clothing showcases")


@clothing_group.command(name="full", description="Create a showcase with 3 shirts and 3 pant options")
@app_commands.describe(
    shirt1="First shirt template image",
    pants1="First pant option image",
    shirt2="Second shirt template image",
    shirt3="Third shirt template image",
    pants2="Second pant option image",
    pants3="Third pant option image",
    type="Layout type. Defaults to portrait.",
)
@app_commands.choices(type=[
    app_commands.Choice(name="Landscape", value="landscape"),
    app_commands.Choice(name="Portrait", value="portrait"),
])
@app_commands.guild_only()
async def showcase_full(
    interaction: discord.Interaction,
    shirt1: discord.Attachment,
    pants1: discord.Attachment,
    shirt2: discord.Attachment,
    shirt3: discord.Attachment,
    pants2: discord.Attachment,
    pants3: discord.Attachment,
    type: app_commands.Choice[str] = "portrait",
):
    await interaction.response.defer()
    try:
        guild = _guild(interaction)
        images = [_open_image(await _attachment_bytes(item)) for item in (shirt1, pants1, shirt2, pants2, shirt3, pants3)]
        pairs = [(images[index], images[index + 1]) for index in range(0, len(images), 2)]
        bg = await _background_for(guild, None)
        output = _compose_pairs(pairs, type.value, "ILE PACKAGES", bg)
        buffer = io.BytesIO()
        output.convert("RGB").save(buffer, format="PNG", optimize=True)
        buffer.seek(0)
        await interaction.followup.send(
            content=f"**ILE PACKAGES** — {type.name} layout",
            file=discord.File(buffer, filename="clothing-showcase.png"),
        )
    except (OSError, ValueError, RuntimeError) as error:
        LOG.warning("Showcase composition failed: %s", error)
        await interaction.followup.send(f"I couldn't create the showcase: {error}", ephemeral=True)


@clothing_group.command(name="single", description="Create a showcase with one shirt and one pant option")
@app_commands.describe(
    shirt="Shirt template image",
    pants="Pant option image",
    type="Layout type. Defaults to portrait.",
)
@app_commands.choices(type=[
    app_commands.Choice(name="Landscape", value="landscape"),
    app_commands.Choice(name="Portrait", value="portrait"),
])
@app_commands.guild_only()
async def showcase_single(
    interaction: discord.Interaction,
    shirt: discord.Attachment,
    pants: discord.Attachment,
    type: app_commands.Choice[str] = "portrait",
):
    await interaction.response.defer()
    try:
        guild = _guild(interaction)
        images = [_open_image(await _attachment_bytes(item)) for item in (shirt, pants)]
        bg = await _background_for(guild, None)
        output = _compose_pairs([tuple(images)], type.value, "ILE CUSTOMS", bg)
        buffer = io.BytesIO()
        output.convert("RGB").save(buffer, format="PNG", optimize=True)
        buffer.seek(0)
        await interaction.followup.send(
            content=f"**ILE CUSTOMS** — {type.name} layout",
            file=discord.File(buffer, filename="clothing-showcase.png"),
        )
    except (OSError, ValueError, RuntimeError) as error:
        LOG.warning("Single showcase composition failed: %s", error)
        await interaction.followup.send(f"I couldn't create the showcase: {error}", ephemeral=True)


@app_commands.command(name="background", description="Set or clear the default clothing showcase background")
@app_commands.describe(image="Upload a background image", url="HTTPS image URL, or leave both blank to clear it")
@app_commands.default_permissions(manage_guild=True)
@app_commands.guild_only()
async def showcase_background(
    interaction: discord.Interaction,
    image: Optional[discord.Attachment] = None,
    url: Optional[str] = None,
):
    guild = _guild(interaction)
    if not interaction.user.guild_permissions.manage_guild and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You need **Manage Server** to change the showcase background.", ephemeral=True)
        return
    if image is not None and url:
        await interaction.response.send_message("Choose an upload or a URL, not both.", ephemeral=True)
        return
    try:
        settings = _settings(guild)
        if image is None and not url:
            settings.pop("background_path", None)
            data = _read_settings()
            data[str(guild.id)] = settings
            _write_settings(data)
            await interaction.response.send_message("The default showcase background was cleared.", ephemeral=True)
            return
        data = await _attachment_bytes(image) if image is not None else _url_bytes(url.strip())
        _open_image(data)
        directory = Path(ASSETS_DIR) / "showcase"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"background-{guild.id}.png"
        path.write_bytes(data)
        settings["background_path"] = str(path)
        data = _read_settings()
        data[str(guild.id)] = settings
        _write_settings(data)
    except (OSError, UnicodeError, ValueError, RuntimeError, urllib.error.URLError) as error:
        LOG.warning("Could not save showcase background: %s", error)
        await interaction.response.send_message(f"I couldn't save that background: {error}", ephemeral=True)
        return
    await interaction.response.send_message("The default clothing showcase background was updated.", ephemeral=True)


showcase_group = app_commands.Group(name="showcase", description="Create showcase images")
showcase_group.add_command(clothing_group)
showcase_group.add_command(showcase_background)

COMMANDS = [showcase_group]
