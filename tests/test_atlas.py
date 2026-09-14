from pathlib import Path
import struct
import unittest
from dataclasses import replace

from shs_runtime.atlas import AtlasFont, SpriteAtlas
from shs_runtime.content import ContentLibrary
from shs_runtime.ui_assets import Raster, UIAssetError


class AtlasTests(unittest.TestCase):
    def test_distinct_abgr_pixels_frames_and_bounds(self):
        data = (struct.pack('>Bhbhhhhh', 16, 1, 0, 0, 0, 0, 1, 2)
                + struct.pack('>h6h',1,1,0,1,2,1,2)
                + bytes([255,30,20,10,128,60,50,40,0,90,80,70,255,120,110,100]))
        atlas=SpriteAtlas.parse(data)
        self.assertEqual(atlas.raster(0),Raster(1,2,bytes([40,50,60,128,100,110,120,255])))
        for bad in (data[:-1],data+b'\0',data[:10]):
            with self.assertRaises(UIAssetError):SpriteAtlas.parse(bad)
        with self.assertRaises(UIAssetError):atlas.raster(-1)
        composite = replace(atlas, parts=(((0, -2, 3),), ((-1, 10, -5), (0, 1, 2))))
        self.assertEqual(composite.literals(-2), ((0, 8, -2), (0, 1, 2)))
        with self.assertRaises(UIAssetError): replace(atlas, parts=(((-1, 0, 0),),)).literals(-1)

    def test_binary_font_case_fallback_and_extents(self):
        atlas=Raster(8,10,b'\0'*(8*10*4))
        data=struct.pack('>BBbhbBhhb',5,1,-1,1,10,65,0,0,8)
        font=AtlasFont.parse(data,atlas)
        self.assertEqual(font.glyph('a'),(0,0,8))
        self.assertIsNone(font.glyph('?'))
        with self.assertRaises(UIAssetError):AtlasFont.parse(data[:-1]+b'\x09',atlas)

    @unittest.skipUnless(Path('.shs-library/library.json').exists(), 'user library absent')
    def test_original_grid_and_football_atlases(self):
        with ContentLibrary(Path('.shs-library')) as lib:
            r=lib.open_episode('The_New_Girl.exp')
            for asset,count in [(290,154),(446,48),(496,1),(499,1),(502,1),(522,1)]:
                atlas=SpriteAtlas.parse(r.read_asset(asset))
                self.assertEqual(len(atlas.frames),count)
                for i in range(count):atlas.raster(i)
                for i in range(len(atlas.parts)):atlas.literals(~i)
            atlas=SpriteAtlas.parse(r.read_asset(522))
            font=AtlasFont.parse(r.read_asset(523),atlas.image)
            self.assertEqual((font.height,len(font.glyphs)),(85,60))
