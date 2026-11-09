"""Clothing template showcase commands.

The image composition is intentionally kept separate from the command wiring so
the feature can also be reused by the standalone launcher in Resources Managament.
"""

from __future__ import annotations

import asyncio
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
    from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
except ImportError:  # pragma: no cover - reported when the command is used
    Image = ImageDraw = ImageFilter = ImageFont = ImageOps = None

SETTINGS_FILE = None
ASSETS_DIR = None
LOG = logging.getLogger("order-center.clothing-showcase")
MAX_IMAGE_BYTES = 12 * 1024 * 1024
LANDSCAPE_SIZE = (1600, 900)
PORTRAIT_SIZE = (1080, 1350)
# Pillow's DecompressionBombError is not an OSError, so it is listed explicitly.
IMAGE_ERRORS = (OSError, ValueError, RuntimeError) + ((Image.DecompressionBombError,) if Image else ())



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
    try:
        return ImageFont.load_default(size)
    except TypeError:  # Pillow < 10.1
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
    return ImageOps.fit(background, size, method=Image.LANCZOS).convert("RGBA")


OUTLINE = 4
GAP = 28


def _draw_image(draw, canvas, image, box):
    """Place a template in box with a white outline that hugs its opaque pixels."""
    left, top, right, bottom = box
    pad = OUTLINE + 2
    fitted, position = _fit(image, (left + pad, top + pad, right - pad, bottom - pad))
    padded = Image.new("RGBA", (fitted.width + OUTLINE * 2, fitted.height + OUTLINE * 2), (0, 0, 0, 0))
    padded.paste(fitted, (OUTLINE, OUTLINE))
    halo = padded.getchannel("A").filter(ImageFilter.MaxFilter(OUTLINE * 2 + 1))
    outline = Image.new("RGBA", padded.size, (255, 255, 255, 255))
    outline.putalpha(halo)
    canvas.alpha_composite(outline, (position[0] - OUTLINE, position[1] - OUTLINE))
    canvas.alpha_composite(fitted, position)


def _title_layer(text: str, size: int):
    """Bold, slanted white title with a soft shadow, like the ILE logo lettering."""
    font = _font(size, bold=True)
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    box = probe.textbbox((0, 0), text, font=font, stroke_width=3)
    w, h = box[2] - box[0] + 40, box[3] - box[1] + 40
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(layer).text((20 - box[0], 20 - box[1]), text, font=font, fill="white", stroke_width=3, stroke_fill="white")
    shear = 0.22
    layer = layer.transform(
        (w + int(h * shear), h), Image.AFFINE, (1, shear, -h * shear, 0, 1, 0), resample=Image.BICUBIC
    )
    shadow = Image.new("RGBA", layer.size, (90, 48, 65, 255))
    shadow.putalpha(layer.getchannel("A").point(lambda v: int(v * 0.55)))
    shadow = shadow.filter(ImageFilter.GaussianBlur(4))
    out = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    out.alpha_composite(shadow, (4, 6))
    out.alpha_composite(layer)
    return out


def _paste_title(canvas, text: str, top: int, size: int):
    layer = _title_layer(text, size)
    canvas.alpha_composite(layer, ((canvas.width - layer.width) // 2, top))
    return top + layer.height


def _logo_layer(height: int):
    path = Path(ASSETS_DIR) / "showcase" / "logo.png" if ASSETS_DIR else None
    if path is not None and path.exists():
        logo = Image.open(path).convert("RGBA")
        return ImageOps.contain(logo, (height * 4, height))
    return _title_layer("ILE", height)


def _compose_pairs(pairs: list[tuple], orientation: str, title: str, background):
    width, height = LANDSCAPE_SIZE if orientation == "landscape" else PORTRAIT_SIZE
    canvas = Image.new("RGBA", (width, height), (245, 203, 218, 255))
    if background is not None:
        canvas = _background_canvas(background, (width, height))
    draw = ImageDraw.Draw(canvas)

    margin = 40
    single = len(pairs) == 1
    landscape = orientation == "landscape"
    content_top = margin
    # A single landscape layout has no title; the logo sits between the two templates.
    if title.strip() and not (single and landscape):
        content_top = _paste_title(canvas, title.strip()[:50], 22, 64 if landscape else 72) + 4

    if single:
        shirt, pants = pairs[0]
        if landscape:
            half = (width - 2 * margin - GAP) // 2
            _draw_image(draw, canvas, shirt, (margin, margin, margin + half, height - margin))
            _draw_image(draw, canvas, pants, (margin + half + GAP, margin, width - margin, height - margin))
            logo = _logo_layer(110)
            canvas.alpha_composite(logo, ((width - logo.width) // 2, height - margin - logo.height - 20))
        else:
            box_height = (height - content_top - margin - GAP) // 2
            _draw_image(draw, canvas, shirt, (margin, content_top, width - margin, content_top + box_height))
            _draw_image(draw, canvas, pants, (margin, content_top + box_height + GAP, width - margin, height - margin))
        return canvas

    if landscape:
        columns = len(pairs)
        box_width = (width - 2 * margin - GAP * (columns - 1)) // columns
        box_height = (height - content_top - margin - GAP) // 2
        for index, (shirt, pants) in enumerate(pairs):
            x = margin + index * (box_width + GAP)
            _draw_image(draw, canvas, shirt, (x, content_top, x + box_width, content_top + box_height))
            _draw_image(draw, canvas, pants, (x, content_top + box_height + GAP, x + box_width, height - margin))
    else:
        box_height = (height - content_top - margin - GAP * (len(pairs) - 1)) // len(pairs)
        half = (width - 2 * margin - GAP) // 2
        for index, (shirt, pants) in enumerate(pairs):
            y = content_top + index * (box_height + GAP)
            _draw_image(draw, canvas, shirt, (margin, y, margin + half, y + box_height))
            _draw_image(draw, canvas, pants, (margin + half + GAP, y, width - margin, y + box_height))
    return canvas


async def _background_bytes(guild: discord.Guild) -> Optional[bytes]:
    saved = _settings(guild).get("background_path")
    if saved:
        path = Path(saved)
        if path.exists():
            return path.read_bytes()
    return None


def _render_showcase(uploads: list[bytes], orientation: str, title: str, background: Optional[bytes]) -> io.BytesIO:
    """CPU-heavy image work, run off the event loop so the gateway heartbeat is not blocked."""
    images = [_open_image(data) for data in uploads]
    pairs = [(images[index], images[index + 1]) for index in range(0, len(images), 2)]
    output = _compose_pairs(pairs, orientation, title, _open_image(background) if background else None)
    buffer = io.BytesIO()
    output.convert("RGB").save(buffer, format="PNG", optimize=True)
    buffer.seek(0)
    return buffer


def _save_guild_settings(guild: discord.Guild, **changes):
    data = _read_settings()
    settings = data.setdefault(str(guild.id), {})
    for key, value in changes.items():
        if value is None:
            settings.pop(key, None)
        else:
            settings[key] = value
    _write_settings(data)


def _guild(interaction: discord.Interaction) -> discord.Guild:
    if interaction.guild is None:
        raise RuntimeError("This command can only be used inside a server.")
    return interaction.guild


clothing_group = app_commands.Group(name="clothing", description="Create clothing showcases")


def _layout_value(choice: Optional[app_commands.Choice[str]]) -> str:
    return choice.value if choice else "portrait"


def _layout_name(choice: Optional[app_commands.Choice[str]]) -> str:
    return choice.name if choice else "Portrait"


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
    type: Optional[app_commands.Choice[str]] = None,
):
    await interaction.response.defer(thinking=True)
    try:
        guild = _guild(interaction)
        uploads = [await _attachment_bytes(item) for item in (shirt1, pants1, shirt2, pants2, shirt3, pants3)]
        background = await _background_bytes(guild)
        buffer = await asyncio.to_thread(_render_showcase, uploads, _layout_value(type), "ILE PACKAGES", background)
        await interaction.followup.send(
            content=f"**ILE PACKAGES** — {_layout_name(type)} layout",
            file=discord.File(buffer, filename="clothing-showcase.png"),
        )
    except IMAGE_ERRORS as error:
        LOG.warning("Showcase composition failed: %s", error)
        await interaction.followup.send(f"I couldn't create the showcase: {error}")


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
    type: Optional[app_commands.Choice[str]] = None,
):
    await interaction.response.defer(thinking=True)
    try:
        guild = _guild(interaction)
        uploads = [await _attachment_bytes(item) for item in (shirt, pants)]
        background = await _background_bytes(guild)
        buffer = await asyncio.to_thread(_render_showcase, uploads, _layout_value(type), "", background)
        await interaction.followup.send(
            content=f"{_layout_name(type)} layout",
            file=discord.File(buffer, filename="clothing-showcase.png"),
        )
    except IMAGE_ERRORS as error:
        LOG.warning("Single showcase composition failed: %s", error)
        await interaction.followup.send(f"I couldn't create the showcase: {error}")


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
    permissions = getattr(interaction.user, "guild_permissions", None)
    if permissions is None or not (permissions.manage_guild or permissions.administrator):
        await interaction.response.send_message("You need **Manage Server** to change the showcase background.", ephemeral=True)
        return
    if image is not None and url:
        await interaction.response.send_message("Choose an upload or a URL, not both.", ephemeral=True)
        return
    # Downloading and validating the image can exceed Discord's 3-second reply window.
    await interaction.response.defer(ephemeral=True, thinking=True)
    try:
        if image is None and not url:
            _save_guild_settings(guild, background_path=None)
            await interaction.followup.send("The default showcase background was cleared.", ephemeral=True)
            return
        if image is not None:
            data = await _attachment_bytes(image)
        else:
            url = url.strip()
            if not url.lower().startswith("https://"):
                raise ValueError("The background URL must start with https://.")
            data = await asyncio.to_thread(_url_bytes, url)
        await asyncio.to_thread(_open_image, data)
        directory = Path(ASSETS_DIR) / "showcase"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"background-{guild.id}.png"
        path.write_bytes(data)
        _save_guild_settings(guild, background_path=str(path))
    except (*IMAGE_ERRORS, UnicodeError, urllib.error.URLError) as error:
        LOG.warning("Could not save showcase background: %s", error)
        await interaction.followup.send(f"I couldn't save that background: {error}", ephemeral=True)
        return
    await interaction.followup.send("The default clothing showcase background was updated.", ephemeral=True)


# Discord ignores guild_only/default_permissions on subcommands, so they are set on the top-level group.
showcase_group = app_commands.Group(name="showcase", description="Create showcase images", guild_only=True)
showcase_group.add_command(clothing_group)
showcase_group.add_command(showcase_background)

COMMANDS = [showcase_group]
