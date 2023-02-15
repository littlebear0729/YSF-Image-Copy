# -*- coding: utf-8 -*-
""" ysf-image-copy

Usage:
  ysf-image-copy.py CALLSIGN RADIOID OUTDIR [-d DIRECTORY|-f PICFILE] [-u] [-t TEXT] [-c COLOUR]
  
Arguments:
  CALLSIGN            The RX location from internal list of RAS sites
  RADIOID             The Radio ID to insert
  OUTDIR              The output directory
  
Options:
  -h --help                          Show this screen
  -v --version                       Show version
  -d DIRECTORY --dir=DIRECTORY       Name the input directory forbatch conversion
  -f PICFILE --file=PICFILE          Convert a single file
  -t TEXT --text=TEXT                Write text over image
  -c COLOUR --colour=COLOUR          Colour for the text
  -u                                 Update files at outdir instead of starting from scratch
  
"""

import io
import binascii
from datetime import datetime, timedelta
import os
import sys
from PIL import Image, ExifTags
from PIL.ExifTags import TAGS, GPSTAGS
from PIL import ImageFont
from PIL import ImageDraw
from colour import Color
from docopt import docopt

print("YSF-Image-Copy Running")


def get_geotagging(exif):
    """Retrieve GPS tags from EXIF

    Args:
        exif (object): EXIF object

    Raises:
        ValueError: if no EXIF data found
        ValueError: if no EXIF geotagging data found

    Returns:
        dict: Dictionary of EXIF tags
    """

    if not exif:
        raise ValueError("No EXIF metadata found")

    geotagging = {}
    for (idx, tag) in TAGS.items():
        if tag == 'GPSInfo':
            if idx not in exif:
                raise ValueError("No EXIF geotagging found")

            for (key, val) in GPSTAGS.items():
                if key in exif[idx]:
                    geotagging[val] = exif[idx][key]

    return geotagging


def encodegps(exif):
    """Take GPS values from EXIF and encode to YSF string

    Args:
        exif (object): EXIF object

    Returns:
        str: String in format for QSOMSGDIR.DAT
    """
    blank_gps = "                    "

    # exif = get_exif(filename)

    if exif:

        # print(f"exif from {filename}:")
        # print(exif)
        try:
            geotags = get_geotagging(exif)
        except ValueError:
            # No EXIF GPS data
            return blank_gps
        try:
            print(f"geotags from image:")
            print(f'[{geotags}]')
            print(geotags['GPSLatitude'])
            print(geotags['GPSLongitude'])
            return '{:1.1}{:03d}{:02d}{:04d}{:1.1}{:03d}{:02d}{:04d}'.format(
                geotags['GPSLatitudeRef'],
                int(geotags['GPSLatitude'][0]),
                int(geotags['GPSLatitude'][1]),
                int(100 * geotags['GPSLatitude'][2]),
                geotags['GPSLongitudeRef'],
                int(geotags['GPSLongitude'][0]),
                int(geotags['GPSLongitude'][1]),
                int(100 * geotags['GPSLongitude'][2]),
            )
        except KeyError:
            # GPS data missing?
            return blank_gps

    return blank_gps


def get_date_taken(exif):
    """Get picture taken time or now()

    Args:
        exif (object): EXIF object

    Returns:
        datetime: The datetime object
    """
    try:
        if exif:
            dto_str = exif[36867]
            return datetime.strptime(dto_str, '%Y:%m:%d %H:%M:%S')
        else:
            return datetime.now()
    except KeyError:
        # No EXIF data for datetime
        return datetime.now()


def getfilesize(filename):
    """Get file size as bytes

    Args:
        filename (str): The full pathname of a file

    Returns:
        bytes: 4-byte field giving file size
    """
    b = os.path.getsize(filename)
    return b.to_bytes(4, byteorder='big', signed=False)


def dec2hex(val):
    """Convert a number such that it reads like decimal when displayed as hex.

    Args:
        val (int): The number

    Returns:
        int: The number encoded to hex
    """
    v = val % 100
    return v % 10 + 16 * (v // 10)


def writedate(binary_stream, when):
    """Write a date to a BytesIO binary stream

    Args:
        binary_stream (object): BytesIO stream
        when (datatime): The date time object to write
    """

    t = when.timetuple()
    for z in t[:6]:
        n = dec2hex(z)
        # print("{:02d} -> {:02d} (0x{:02x})".format(z,n,n))
        binary_stream.write(n.to_bytes(1, byteorder='big', signed=False))


def print_output(binary_stream, chunksize):
    binary_stream.seek(0)
    while binary_stream.readable():
        addr = binary_stream.tell()
        d = binary_stream.read(chunksize)
        if len(d) == 0:
            break
        print("{:04x}".format(addr), " ".join(["{:02x}".format(x) for x in d]))


def picfilename(radio_id, seq_num):
    """Generate picture file name

    Args:
        radio_id (str): Radio ID to embed
        seq_num (int): Picture number in sequence from 1

    Returns:
        str: Picture file name
    """
    return "H{:.5}{:06d}.jpg".format(radio_id, seq_num)


def write_log(binary_stream, picfile, call_sign, radio_id, outdir, picnum, text, colour):
    """Write an entry for QSOMSGLOG.DAT

    This writes a single entry to the binary stream, which will ultimately be
    written out to QSOMSGLOG.DAT

    Args:
        binary_stream (object): BytesIO buffer to which entries are
        picfile (str): File location of input picture file
        call_sign (str): Call sign to embed
        radio_id (str): Radio ID to embed
        outdir (str): Output directory location
        picnum (int): Picture number in sequence, from 1
        text (str): Text to write over the picture or None
        colour (str): String describing the colour for the text
    """
    print(f'Write log entry for {picfile}')
    image = Image.open(picfile)
    exif = image.getexif()
    binary_stream.write(bytes(b'\x00\x00\x00\x00'))  # Head
    binary_stream.write(bytes(b'\x20\x20\x20\x20\x20'))  # Node ID
    binary_stream.write(bytes('ALL       ', 'ASCII'))  # Dest
    binary_stream.write(bytes('      ', 'ASCII'))  # 6 spaces
    binary_stream.write(bytes(radio_id, 'ASCII'))  # Radio ID
    binary_stream.write(bytes(call_sign.ljust(16), 'ASCII'))  # Callsign in 16-char field
    writedate(binary_stream, datetime.now() - timedelta(hours=1))
    writedate(binary_stream, datetime.now())
    taken = get_date_taken(exif)
    writedate(binary_stream, taken)
    binary_stream.write(
        bytes('{:11.11}'.format(os.path.basename(picfile)), 'ASCII')
    )  # Description
    binary_stream.write(bytes('     ', 'ASCII'))  # 5 spaces
    outname = picfilename(radio_id, picnum)
    # Ensure the PHOTO directory exists
    photodir = os.path.join(outdir, 'PHOTO')
    if not os.path.exists(photodir):
        os.makedirs(photodir)
    fulloutname = os.path.join(photodir, outname)
    print(f'Convert {picfile} -> {outname}')
    shrink_image(image, fulloutname, text, colour)
    binary_stream.write(getfilesize(fulloutname))
    binary_stream.write(bytes(outname, 'ASCII'))  # Filename
    binary_stream.write(bytes(encodegps(exif), 'ASCII'))  # GPS
    binary_stream.write(bytes('        ', 'ASCII'))  # 8 spaces


def paint_text(img, text, tcolour):
    """Taking a PIL image object write some text over it.

    Any '\' characters are replaced by newline.

    The text colour is interpretted using the Colour module.

    Args:
        img (PIL object): The image to draw over
        text (str): The text to draw
        tcolour (str): A string describing the colour
    """
    # Get drawing context
    draw = ImageDraw.Draw(img)
    # Amble-Bold will be included in distribution
    try:
        font = ImageFont.truetype('Amble-Bold.ttf', 48)
    except OSError:
        font = ImageFont.truetype(
            os.path.join(get_script_path(), 'Amble-Bold.ttf'), 48)
    with_newlines = text.replace('\\', '\n')
    c = Color(tcolour)
    ct = tuple(int(255 * v) for v in c.rgb)
    draw.text((5, 5), with_newlines, ct, font=font)


def shrink_image(image, saveto, text, colour):
    """Shrink the image to a 320x240 thumbnail and save to file.

    Args:
        image (PIL image): The original image object
        saveto (str): The location for saving the image
        text (str): A string to write over the image or None
        colour (str): A string describing the colour to use for the text
    """
    print(f'Write -> {saveto}')
    image.thumbnail((320, 240))
    if text != None:
        paint_text(image, text, colour)
    image.save(saveto)


def write_fat(outdir, pic_count):
    """Write the QSOPCTFAT.DAT file.

    This file stores lengths and address offsets into the QSOMSGDIR.DAT file
    for the location of each picture. 

    Args:
        outdir (str): Path to the directory for writing QSOPCTFAT.DAT
        pic_count (int): The number of pictures
    """
    with open(os.path.join(outdir, 'QSOLOG', 'QSOPCTFAT.DAT'), 'wb') as f:
        for pnum in range(pic_count):
            f.write(bytes(b'\x40'))
            addr = 0X80 * pnum
            f.write(addr.to_bytes(3, byteorder='big', signed=False))


def write_mng(outdir, msg_count, pic_count, grp_count):
    """Write the QSOMNG.DAT file.

    This file tracks the numbers of messages, photos and GM groups stored.

    Args:
        outdir (str): Path to the directory for writing QSOMNG.DAT
        msg_count (int): The number of messages
        pic_count (int): The number of pictures
        grp_count (int): The number of groups
    """
    with open(os.path.join(outdir, 'QSOLOG', 'QSOMNG.DAT'), 'wb') as f:
        f.write(msg_count.to_bytes(2, byteorder='big', signed=False))
        f.write(bytes(b'\xff' * 14))  # Padding
        f.write(pic_count.to_bytes(2, byteorder='big', signed=False))
        f.write(grp_count.to_bytes(2, byteorder='big', signed=False))
        f.write(bytes(b'\xff' * 12))  # Padding


def get_script_path():
    """Get the script path

    Returns:
        str: The script path
    """
    return os.path.dirname(os.path.realpath(sys.argv[0]))


def main(callsign, radioid, outdir, file_name):
    dir_name = None
    text = None
    colour = None

    if colour == None:
        colour = 'red'

    pic_count = 0

    with io.BytesIO() as bs:
        if file_name:
            write_log(bs, file_name, callsign, radioid, outdir, pic_count + 1, text, colour)
            pic_count += 1

        if dir_name:
            for filename in os.listdir(dir_name):
                try:
                    fullfname = os.path.join(dir_name, filename)
                    write_log(bs, fullfname, callsign, radioid, outdir, pic_count + 1, text, colour)
                    pic_count += 1
                except IOError as e:
                    print("cannot convert", filename, e)

        if pic_count > 0:
            # At least one picture written
            # Ensure the QSOLOG directory exists
            logdir = os.path.join(outdir, 'QSOLOG')
            if not os.path.exists(logdir):
                os.makedirs(logdir)
            with open(os.path.join(logdir, 'QSOPCTDIR.DAT'), 'wb') as f:
                f.write(bs.getvalue())

            write_fat(outdir, pic_count)
            write_mng(outdir, 0, pic_count, 0)
