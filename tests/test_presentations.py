from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from xml.etree import ElementTree as ET
from copy import deepcopy
from pathlib import Path
from unittest import mock

from webpentestkit.models import FindingInput
from webpentestkit.gui.controller import GuiController
from webpentestkit.presentation_engine import (
    PROFILE_FORMAT_VERSION,
    analyze_template,
    build_render_plan,
    format_sequence,
    format_binding_value,
    normalize_sequence_formatter,
    sequence_formatter_from_template,
    sequence_formatter_template,
    reconcile_template_profile,
    render_presentation,
    template_digest,
    validate_profile,
    validate_pptx,
)
from webpentestkit.presentation_engine.renderer import _set_text
from webpentestkit.errors import KitError
from webpentestkit.presentation_library import PresentationTemplateLibrary
from webpentestkit.services import ProjectService
from webpentestkit.presentation_engine import renderer as renderer_module


PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\rIDAT\x08\xd7c\xf8\xcf\xc0\xf0\x1f\x00\x05"
    b"\x00\x01\xff\x89\x99=\x1d\x00\x00\x00\x00IEND\xaeB`\x82"
)


def create_template(path: Path, *, include_notes: bool = False) -> None:
    parts = {
        "[Content_Types].xml": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="png" ContentType="image/png"/>
  <Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
  <Override PartName="/ppt/slides/slide1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>
  <Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>
  <Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>
  <Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>
</Types>""",
        "_rels/.rels": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
</Relationships>""",
        "ppt/presentation.xml": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>
  <p:sldIdLst><p:sldId id="256" r:id="rId2"/></p:sldIdLst>
  <p:sldSz cx="12192000" cy="6858000" type="screen16x9"/>
  <p:notesSz cx="6858000" cy="9144000"/>
</p:presentation>""",
        "ppt/_rels/presentation.xml.rels": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide1.xml"/>
</Relationships>""",
        "ppt/slides/slide1.xml": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld><p:spTree>
    <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/>
    <p:sp><p:nvSpPr><p:cNvPr id="2" name="Title"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
      <p:spPr><a:xfrm><a:off x="500000" y="300000"/><a:ext cx="6000000" cy="800000"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr>
      <p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:rPr lang="ko-KR"/><a:t>Template title</a:t></a:r></a:p></p:txBody>
    </p:sp>
    <p:pic><p:nvPicPr><p:cNvPr id="3" name="Evidence"/><p:cNvPicPr/><p:nvPr/></p:nvPicPr>
      <p:blipFill><a:blip r:embed="rId2"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>
      <p:spPr><a:xfrm><a:off x="500000" y="1500000"/><a:ext cx="6000000" cy="4000000"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr>
    </p:pic>
    <p:sp><p:nvSpPr><p:cNvPr id="4" name="Evidence frame"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
      <p:spPr><a:xfrm><a:off x="7000000" y="1500000"/><a:ext cx="4000000" cy="3000000"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr>
      <p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:rPr lang="ko-KR"/><a:t>Evidence image</a:t></a:r></a:p></p:txBody>
    </p:sp>
  </p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sld>""",
        "ppt/slides/_rels/slide1.xml.rels": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/image1.png"/>
</Relationships>""",
        "ppt/slideLayouts/slideLayout1.xml": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" type="blank"><p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/></p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>""",
        "ppt/slideLayouts/_rels/slideLayout1.xml.rels": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/></Relationships>""",
        "ppt/slideMasters/slideMaster1.xml": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/></p:spTree></p:cSld><p:clrMap accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" bg1="lt1" bg2="lt2" folHlink="folHlink" hlink="hlink" tx1="dk1" tx2="dk2"/><p:sldLayoutIdLst><p:sldLayoutId id="1" r:id="rId1"/></p:sldLayoutIdLst><p:txStyles/></p:sldMaster>""",
        "ppt/slideMasters/_rels/slideMaster1.xml.rels": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/></Relationships>""",
        "ppt/theme/theme1.xml": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Test"><a:themeElements><a:clrScheme name="Test"><a:dk1><a:srgbClr val="000000"/></a:dk1><a:lt1><a:srgbClr val="FFFFFF"/></a:lt1><a:dk2><a:srgbClr val="000000"/></a:dk2><a:lt2><a:srgbClr val="FFFFFF"/></a:lt2><a:accent1><a:srgbClr val="4472C4"/></a:accent1><a:accent2><a:srgbClr val="ED7D31"/></a:accent2><a:accent3><a:srgbClr val="A5A5A5"/></a:accent3><a:accent4><a:srgbClr val="FFC000"/></a:accent4><a:accent5><a:srgbClr val="5B9BD5"/></a:accent5><a:accent6><a:srgbClr val="70AD47"/></a:accent6><a:hlink><a:srgbClr val="0563C1"/></a:hlink><a:folHlink><a:srgbClr val="954F72"/></a:folHlink></a:clrScheme><a:fontScheme name="Test"><a:majorFont><a:latin typeface="Arial"/><a:ea typeface="Arial"/><a:cs typeface="Arial"/></a:majorFont><a:minorFont><a:latin typeface="Arial"/><a:ea typeface="Arial"/><a:cs typeface="Arial"/></a:minorFont></a:fontScheme><a:fmtScheme name="Test"><a:fillStyleLst/><a:lnStyleLst/><a:effectStyleLst/><a:bgFillStyleLst/></a:fmtScheme></a:themeElements></a:theme>""",
    }
    if include_notes:
        content_types = parts["[Content_Types].xml"]
        parts["[Content_Types].xml"] = content_types.replace(
            "</Types>",
            '  <Override PartName="/ppt/notesSlides/notesSlide1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.notesSlide+xml"/>\n</Types>',
        )
        slide_relationships = parts["ppt/slides/_rels/slide1.xml.rels"]
        parts["ppt/slides/_rels/slide1.xml.rels"] = slide_relationships.replace(
            "</Relationships>",
            '  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesSlide" Target="../notesSlides/notesSlide1.xml"/>\n</Relationships>',
        )
        parts["ppt/notesSlides/notesSlide1.xml"] = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:notes xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/></p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:notes>"""
        parts["ppt/notesSlides/_rels/notesSlide1.xml.rels"] = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="../slides/slide1.xml"/></Relationships>"""
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, value in parts.items():
            archive.writestr(name, value)
        archive.writestr("ppt/media/image1.png", PNG_1X1)


def profile_for(template: Path) -> dict:
    return {
        "formatVersion": 1,
        "id": "test-template",
        "name": "Test template",
        "templateHash": template_digest(template),
        "story": {"document": [], "finding": ["finding-detail"]},
        "layouts": [
            {
                "id": "finding-one-image",
                "role": "finding-detail",
                "sourceSlide": 1,
                "capacity": {"evidence": 1},
                "bindings": {
                    "title": {"kind": "text", "shapeId": 2, "maxChars": 80},
                    "evidence.0": {"kind": "image", "shapeId": 4, "fit": "cover"},
                },
            }
        ],
    }


class PresentationEngineTest(unittest.TestCase):
    def test_text_binding_collapses_template_sample_runs(self) -> None:
        drawing = "http://schemas.openxmlformats.org/drawingml/2006/main"
        presentation = (
            "http://schemas.openxmlformats.org/presentationml/2006/main"
        )
        shape = ET.fromstring(
            f"""
            <p:sp xmlns:p="{presentation}" xmlns:a="{drawing}">
              <p:txBody>
                <a:bodyPr><a:noAutofit/></a:bodyPr><a:lstStyle/>
                <a:p>
                  <a:pPr marL="85725" indent="-85725"/>
                  <a:r><a:rPr b="1"/><a:t>요약</a:t></a:r>
                  <a:r><a:rPr/><a:t>☞ </a:t></a:r>
                  <a:r><a:rPr/><a:t>발생 URL</a:t></a:r>
                  <a:endParaRPr/>
                </a:p>
                <a:p><a:r><a:rPr/><a:t>stale paragraph</a:t></a:r></a:p>
              </p:txBody>
            </p:sp>
            """
        )

        value = "https://portal.example.test/login?returnUrl={url}"
        self.assertTrue(_set_text(shape, value))
        self.assertEqual(
            [item.text for item in shape.findall(f".//{{{drawing}}}t")],
            [value],
        )
        self.assertEqual(len(shape.findall(f".//{{{drawing}}}p")), 1)
        runs = shape.findall(f".//{{{drawing}}}r")
        self.assertEqual(len(runs), 1)
        self.assertEqual(
            runs[0].find(f"./{{{drawing}}}rPr").get("b"),
            "1",
        )
        body = shape.find(f".//{{{drawing}}}bodyPr")
        self.assertIsNotNone(body.find(f"./{{{drawing}}}normAutofit"))
        self.assertIsNone(body.find(f"./{{{drawing}}}noAutofit"))

    def test_template_workspace_controller_operations_do_not_require_project(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            template = root / "template.pptx"
            profile_path = root / "template.otter-profile.json"
            copy_path = root / "profile-copy.json"
            create_template(template)
            controller = GuiController(root / "knowledge.db")

            analysis = controller.analyze_presentation_template(template)
            self.assertEqual(analysis["template"]["slideCount"], 1)
            controller.create_presentation_profile(template, profile_path)
            profile = controller.load_presentation_profile(profile_path)
            self.assertEqual(profile["formatVersion"], PROFILE_FORMAT_VERSION)
            controller.save_presentation_profile(profile, copy_path)
            self.assertTrue(copy_path.is_file())

    def test_template_library_tracks_reusable_profile_and_template_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            template = root / "template.pptx"
            create_template(template)
            profile_path = root / "profile.json"
            profile_path.write_text(
                json.dumps(profile_for(template), ensure_ascii=False),
                encoding="utf-8",
            )
            library = PresentationTemplateLibrary(root / "library")
            registered = library.register(template, profile_path)
            self.assertEqual(registered["status"], "ready")
            self.assertTrue(registered["managed"])
            self.assertEqual(registered["version"], 1)
            self.assertNotEqual(Path(registered["templatePath"]), template)
            self.assertEqual(library.list_entries()[0]["layoutCount"], 1)
            template.write_bytes(template.read_bytes() + b"changed")
            self.assertEqual(library.list_entries()[0]["status"], "ready")
            changed_profile = profile_for(Path(registered["templatePath"]))
            changed_profile["name"] = "Test template v2"
            profile_path.write_text(
                json.dumps(changed_profile, ensure_ascii=False),
                encoding="utf-8",
            )
            published = library.register(
                Path(registered["templatePath"]), profile_path
            )
            self.assertEqual(published["version"], 2)
            self.assertEqual(published["versionCount"], 2)
            latest_from_old_paths = library.find_by_paths(
                registered["templatePath"],
                registered["profilePath"],
            )
            self.assertIsNotNone(latest_from_old_paths)
            self.assertEqual(latest_from_old_paths["id"], registered["id"])
            self.assertEqual(latest_from_old_paths["version"], 2)
            self.assertEqual(
                latest_from_old_paths["profilePath"], published["profilePath"]
            )
            library.remove(registered["id"])
            self.assertEqual(library.list_entries(), [])

    def test_template_library_migrates_legacy_paths_into_managed_storage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            template = root / "legacy.pptx"
            profile_path = root / "legacy-profile.json"
            create_template(template)
            profile_path.write_text(
                json.dumps(profile_for(template), ensure_ascii=False),
                encoding="utf-8",
            )
            library_root = root / "library"
            library_root.mkdir()
            (library_root / "templates.json").write_text(
                json.dumps(
                    {
                        "formatVersion": 1,
                        "templates": [
                            {
                                "id": "legacy",
                                "name": "Legacy",
                                "templatePath": str(template),
                                "profilePath": str(profile_path),
                                "templateHash": template_digest(template),
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            library = PresentationTemplateLibrary(library_root)
            entry = library.list_entries()[0]

            self.assertTrue(entry["managed"])
            self.assertEqual(entry["version"], 1)
            self.assertTrue(Path(entry["templatePath"]).is_file())
            self.assertTrue(Path(entry["profilePath"]).is_file())
            self.assertEqual(
                json.loads((library_root / "templates.json").read_text(encoding="utf-8"))[
                    "formatVersion"
                ],
                2,
            )

    def test_changed_template_mapping_is_reviewable_and_blocks_planning(self) -> None:
        profile = {
            "formatVersion": PROFILE_FORMAT_VERSION,
            "id": "reconcile",
            "name": "Reconcile",
            "templateHash": "a" * 64,
            "families": [{"id": "finding", "name": "Finding"}],
            "storyRecipe": {
                "document": [],
                "finding": [
                    {
                        "id": "finding-overview",
                        "role": "finding-overview",
                        "repeat": "once",
                        "when": "always",
                    }
                ],
                "appendix": [],
            },
            "templateSnapshot": {
                "slideSize": {"cx": 1000, "cy": 500},
                "slides": [
                    {
                        "number": 1,
                        "shapes": [
                            {
                                "id": 2,
                                "name": "Title",
                                "kind": "text",
                                "text": "Finding title",
                                "x": 10,
                                "y": 10,
                                "cx": 500,
                                "cy": 80,
                            }
                        ],
                    }
                ],
            },
            "layouts": [
                {
                    "id": "finding",
                    "familyId": "finding",
                    "role": "finding-overview",
                    "variant": {
                        "kind": "primary",
                        "textDensity": "regular",
                        "priority": 0,
                        "conditions": {},
                    },
                    "sourceSlide": 1,
                    "bindings": {
                        "title": {
                            "kind": "text",
                            "shapeId": 2,
                            "shapeFingerprint": {
                                "name": "Title",
                                "kind": "text",
                                "text": "Finding title",
                                "x": 10,
                                "y": 10,
                                "cx": 500,
                                "cy": 80,
                            },
                        }
                    },
                }
            ],
        }
        analysis = {
            "template": {"sha256": "b" * 64, "slideSize": {"cx": 1000, "cy": 500}},
            "slides": [
                {
                    "number": 1,
                    "shapes": [
                        {
                            "id": 7,
                            "name": "Title",
                            "kind": "text",
                            "text": "Finding title",
                            "x": 10,
                            "y": 10,
                            "cx": 500,
                            "cy": 80,
                        }
                    ],
                }
            ],
        }
        result = reconcile_template_profile(profile, analysis)
        self.assertEqual(result["report"]["review"], 1)
        self.assertEqual(
            result["profile"]["layouts"][0]["bindings"]["title"]["shapeId"],
            7,
        )
        with self.assertRaises(KitError) as error:
            build_render_plan(
                {
                    "formatVersion": 2,
                    "project": {},
                    "summary": {},
                    "targets": [],
                    "assets": [],
                    "findings": [],
                },
                result["profile"],
            )
        self.assertEqual(error.exception.code, "PRESENTATION_PROFILE_REVIEW_REQUIRED")

    def test_renderer_skips_excluded_plan_pages(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            template = root / "template.pptx"
            create_template(template)
            report_ir = {
                "formatVersion": 2,
                "project": {},
                "summary": {},
                "targets": [],
                "assets": [],
                "findings": [
                    {
                        "id": "WEB-01-001",
                        "title": "Rendered finding title",
                        "evidence": [],
                        "procedure": {"steps": []},
                        "technical": {},
                        "retests": [],
                    }
                ],
            }
            profile = profile_for(template)
            plan = build_render_plan(report_ir, profile)
            second = deepcopy(plan["pages"][0])
            second["id"] = "page-0002"
            second["values"]["title"] = "Included page"
            second["included"] = True
            plan["pages"][0]["included"] = False
            second["blocks"] = [
                {
                    "id": "block-1",
                    "kind": "procedure-step",
                    "values": {},
                    "evidence": [{"id": "block-evidence"}],
                }
            ]
            plan["pages"].append(second)
            output = root / "included-only.pptx"
            render_presentation(template, profile, plan, output, project_root=root)
            self.assertEqual(validate_pptx(output)["slideCount"], 1)
            manifest = json.loads(
                output.with_suffix(".pptx.manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["slideCount"], 1)
            self.assertEqual([page["id"] for page in manifest["pages"]], ["page-0002"])

            self.assertEqual(

                manifest["pages"][0]["evidence"],
                ["block-evidence"],
            )
    def test_renderer_drops_source_notes_relationships_from_cloned_slides(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            template = root / "template-with-notes.pptx"
            create_template(template, include_notes=True)
            report_ir = {
                "formatVersion": 2,
                "project": {},
                "summary": {},
                "targets": [],
                "assets": [],
                "findings": [
                    {
                        "id": "WEB-01-001",
                        "title": "First",
                        "evidence": [],
                        "procedure": {"steps": []},
                        "technical": {},
                        "retests": [],
                    }
                ],
            }
            profile = profile_for(template)
            plan = build_render_plan(report_ir, profile)
            second = deepcopy(plan["pages"][0])
            second["id"] = "page-0002"
            second["values"]["title"] = "Second"
            plan["pages"].append(second)
            output = root / "rendered.pptx"

            render_presentation(template, profile, plan, output, project_root=root)

            with zipfile.ZipFile(output) as archive:
                for index in (1, 2):
                    relationships = ET.fromstring(
                        archive.read(f"ppt/slides/_rels/slide{index}.xml.rels")
                    )
                    self.assertFalse(
                        any(
                            str(item.get("Type", "")).endswith("/notesSlide")
                            for item in relationships
                        )
                    )
            self.assertEqual(validate_pptx(output)["slideCount"], 2)

    def test_legacy_profile_migrates_and_quarantines_unknown_bindings(self) -> None:
        value = {
            "formatVersion": 1,
            "id": "legacy",
            "name": "Legacy",
            "templateHash": "a" * 64,
            "story": {
                "document": ["cover", "custom-page"],
                "finding": ["finding-detail"],
            },
            "layouts": [
                {
                    "id": "cover",
                    "role": "cover",
                    "sourceSlide": 1,
                    "bindings": {
                        "title": {"kind": "text", "shapeId": 2},
                        "anything": {"kind": "text", "shapeId": 3},
                    },
                },
                {
                    "id": "custom",
                    "role": "custom-page",
                    "sourceSlide": 2,
                    "bindings": {},
                },
            ],
        }
        migrated = validate_profile(value)
        self.assertEqual(migrated["formatVersion"], PROFILE_FORMAT_VERSION)
        self.assertEqual(list(migrated["layouts"][0]["bindings"]), ["title"])
        self.assertEqual(len(migrated["legacyCompatibility"]["bindings"]), 1)
        self.assertEqual(len(migrated["legacyCompatibility"]["layouts"]), 1)
        self.assertEqual(
            migrated["legacyCompatibility"]["storyRoles"],
            [{"group": "document", "role": "custom-page"}],
        )

    def test_profile_contract_rejects_unknown_role_slot_and_kind(self) -> None:
        base = {
            "formatVersion": PROFILE_FORMAT_VERSION,
            "id": "strict",
            "name": "Strict",
            "templateHash": "a" * 64,
            "families": [],
            "storyRecipe": {"document": [], "finding": [], "appendix": []},
            "layouts": [],
        }
        unknown_role = json.loads(json.dumps(base))
        unknown_role["layouts"] = [
            {"id": "bad", "role": "custom", "sourceSlide": 1, "bindings": {}}
        ]
        with self.assertRaises(KitError) as role_error:
            validate_profile(unknown_role)
        self.assertEqual(role_error.exception.code, "PRESENTATION_ROLE_INVALID")

        unknown_slot = json.loads(json.dumps(base))
        unknown_slot["layouts"] = [
            {
                "id": "bad",
                "role": "cover",
                "sourceSlide": 1,
                "bindings": {"summary": {"kind": "text", "shapeId": 2}},
            }
        ]
        with self.assertRaises(KitError) as slot_error:
            validate_profile(unknown_slot)
        self.assertEqual(slot_error.exception.code, "PRESENTATION_SLOT_INVALID")

        wrong_kind = json.loads(json.dumps(base))
        wrong_kind["layouts"] = [
            {
                "id": "bad",
                "role": "finding-result",
                "sourceSlide": 1,
                "bindings": {"evidence.0": {"kind": "text", "shapeId": 2}},
            }
        ]
        with self.assertRaises(KitError) as kind_error:
            validate_profile(wrong_kind)
        self.assertEqual(kind_error.exception.code, "PRESENTATION_SLOT_KIND_MISMATCH")

    def test_profile_contract_rejects_noncontiguous_evidence_slots(self) -> None:
        value = {
            "formatVersion": PROFILE_FORMAT_VERSION,
            "id": "strict",
            "name": "Strict",
            "templateHash": "a" * 64,
            "families": [],
            "storyRecipe": {"document": [], "finding": [], "appendix": []},
            "layouts": [
                {
                    "id": "finding",
                    "role": "finding-result",
                    "sourceSlide": 1,
                    "bindings": {
                        "title": {"kind": "text", "shapeId": 2},
                        "evidence.1": {"kind": "image", "shapeId": 3},
                    },
                }
            ],
        }
        with self.assertRaises(KitError) as error:
            validate_profile(value)
        self.assertEqual(error.exception.code, "PRESENTATION_EVIDENCE_SLOTS_NONCONTIGUOUS")

    def test_sequence_formatter_is_safe_and_scoped_to_number_fields(self) -> None:
        self.assertEqual(
            format_sequence(
                3,
                {
                    "type": "sequence",
                    "style": "decimal",
                    "padding": 2,
                    "prefix": "STEP ",
                },
            ),
            "STEP 03",
        )
        self.assertEqual(
            format_sequence(2, {"type": "sequence", "style": "circled"}),
            "②",
        )
        self.assertEqual(
            format_sequence(3, {"type": "sequence", "style": "hangul"}),
            "다",
        )
        direct = sequence_formatter_from_template("STEP {number:02}")
        self.assertEqual(format_sequence(3, direct), "STEP 03")
        self.assertEqual(sequence_formatter_template(direct), "STEP {number:02}")
        self.assertEqual(
            format_sequence(
                2, sequence_formatter_from_template("절차 {number:hangul}")
            ),
            "절차 나",
        )
        self.assertEqual(
            format_sequence(
                4,
                {
                    "type": "sequence",
                    "style": "custom",
                    "template": "절차 {number}",
                },
            ),
            "절차 4",
        )
        with self.assertRaises(KitError) as token_error:
            normalize_sequence_formatter(
                {
                    "type": "sequence",
                    "style": "custom",
                    "template": "STEP {value}",
                }
            )
        self.assertEqual(
            token_error.exception.code,
            "PRESENTATION_SEQUENCE_TEMPLATE_INVALID",
        )
        with self.assertRaises(KitError):
            sequence_formatter_from_template("STEP {value}")

        profile = {
            "formatVersion": PROFILE_FORMAT_VERSION,
            "id": "formatter",
            "name": "Formatter",
            "templateHash": "a" * 64,
            "families": [{"id": "procedure", "name": "Procedure"}],
            "storyRecipe": {"document": [], "finding": [], "appendix": []},
            "layouts": [
                {
                    "id": "procedure",
                    "familyId": "procedure",
                    "role": "finding-procedure",
                    "sourceSlide": 1,
                    "composition": {"itemCapacity": 1},
                    "variant": {
                        "kind": "primary",
                        "textDensity": "regular",
                        "priority": 0,
                        "conditions": {},
                    },
                    "bindings": {
                        "items.0.stepNumber": {
                            "kind": "text",
                            "shapeId": 2,
                            "formatter": {
                                "type": "sequence",
                                "style": "decimal",
                                "padding": 2,
                                "prefix": "STEP ",
                            },
                        }
                    },
                },
                {
                    "id": "result",
                    "familyId": "procedure",
                    "role": "finding-result",
                    "sourceSlide": 1,
                    "variant": {
                        "kind": "primary",
                        "priority": 0,
                        "conditions": {},
                    },
                    "bindings": {
                        "findingNumber": {
                            "kind": "text",
                            "shapeId": 2,
                            "formatter": {
                                "type": "sequence",
                                "style": "decimal",
                                "padding": 2,
                                "prefix": "취약점-",
                            },
                        }
                    },
                },
            ],
        }
        validated = validate_profile(profile)
        self.assertEqual(
            validated["layouts"][0]["bindings"]["items.0.stepNumber"][
                "formatter"
            ]["prefix"],
            "STEP ",
        )
        invalid_slot = deepcopy(profile)
        finding_number_binding = validated["layouts"][1]["bindings"][
            "findingNumber"
        ]
        self.assertEqual(
            format_binding_value("findingNumber", 3, finding_number_binding),
            "취약점-03",
        )
        invalid_slot["layouts"][0]["bindings"] = {
            "items.0.stepTitle": {
                "kind": "text",
                "shapeId": 2,
                "formatter": {
                    "type": "sequence",
                    "style": "decimal",
                },
            }
        }
        with self.assertRaises(KitError) as slot_error:
            validate_profile(invalid_slot)
        self.assertEqual(
            slot_error.exception.code,
            "PRESENTATION_FORMATTER_SLOT_INVALID",
        )

    def test_v2_profile_migrates_overflow_roles_to_variants(self) -> None:
        value = {
            "formatVersion": 2,
            "id": "v2",
            "name": "V2",
            "templateHash": "a" * 64,
            "story": {
                "document": [],
                "finding": ["finding-detail", "finding-procedure", "finding-retest"],
            },
            "layouts": [
                {
                    "id": "overview",
                    "role": "finding-detail",
                    "sourceSlide": 1,
                    "bindings": {"title": {"kind": "text", "shapeId": 2}},
                },
                {
                    "id": "procedure-more",
                    "role": "finding-procedure-evidence",
                    "sourceSlide": 2,
                    "bindings": {
                        "evidence.0": {"kind": "image", "shapeId": 4}
                    },
                },
            ],
        }
        migrated = validate_profile(value)
        self.assertEqual(migrated["formatVersion"], PROFILE_FORMAT_VERSION)
        self.assertEqual(migrated["layouts"][0]["role"], "finding-overview")
        self.assertEqual(migrated["layouts"][1]["role"], "finding-procedure")
        self.assertEqual(
            migrated["layouts"][1]["variant"]["kind"], "continuation"
        )
        self.assertEqual(
            [node["role"] for node in migrated["storyRecipe"]["finding"]],
            ["finding-overview", "finding-procedure", "finding-retest"],
        )


    def test_renderer_applies_finding_number_formatter(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            template = root / "template.pptx"
            create_template(template)
            profile = {
                "formatVersion": PROFILE_FORMAT_VERSION,
                "id": "finding-number",
                "name": "Finding number",
                "templateHash": template_digest(template),
                "families": [{"id": "result", "name": "Result"}],
                "storyRecipe": {
                    "document": [],
                    "finding": [
                        {
                            "id": "result",
                            "role": "finding-result",
                            "repeat": "once",
                            "when": "has-data",
                        }
                    ],
                    "appendix": [],
                },
                "layouts": [
                    {
                        "id": "result",
                        "familyId": "result",
                        "role": "finding-result",
                        "sourceSlide": 1,
                        "variant": {
                            "kind": "primary",
                            "priority": 0,
                            "conditions": {},
                        },
                        "bindings": {
                            "findingNumber": {
                                "kind": "text",
                                "shapeId": 2,
                                "formatter": sequence_formatter_from_template(
                                    "취약점-{number:02}"
                                ),
                            }
                        },
                    }
                ],
            }
            report_ir = {
                "formatVersion": 2,
                "project": {},
                "presentation": {},
                "summary": {},
                "targets": [],
                "assets": [],
                "findings": [
                    {
                        "id": "WEB-01-001",
                        "findingNumber": 1,
                        "summary": "Confirmed",
                        "technical": {},
                        "procedure": {"steps": []},
                        "retests": [],
                    },
                    {
                        "id": "WEB-01-002",
                        "findingNumber": 2,
                        "summary": "Confirmed again",
                        "technical": {},
                        "procedure": {"steps": []},
                        "retests": [],
                    }
                ],
            }
            plan = build_render_plan(report_ir, profile)
            output = root / "formatted.pptx"
            render_presentation(template, profile, plan, output, project_root=root)
            with zipfile.ZipFile(output) as archive:
                first = archive.read("ppt/slides/slide1.xml").decode("utf-8")
                second = archive.read("ppt/slides/slide2.xml").decode("utf-8")
            self.assertIn("취약점-01", first)
            self.assertIn("취약점-02", second)

    def test_v4_profile_migrates_to_layout_set_recipe_contract(self) -> None:
        migrated = validate_profile(
            {
                "formatVersion": 4,
                "id": "v4",
                "name": "V4",
                "templateHash": "a" * 64,
                "families": [],
                "storyRecipe": {"document": [], "finding": [], "appendix": []},
                "layouts": [],
            }
        )
        self.assertEqual(migrated["formatVersion"], PROFILE_FORMAT_VERSION)
        self.assertEqual(
            migrated["legacyCompatibility"]["sourceFormatVersion"],
            4,
        )

    def test_story_layout_set_controls_selection_without_text_capacity(self) -> None:
        def layout(layout_id: str, family_id: str) -> dict:
            return {
                "id": layout_id,
                "familyId": family_id,
                "role": "finding-overview",
                "sourceSlide": 1,
                "variant": {
                    "kind": "primary",
                    "priority": 0,
                    "conditions": {},
                },
                "bindings": {"title": {"kind": "text", "shapeId": 2}},
            }

        profile = {
            "formatVersion": PROFILE_FORMAT_VERSION,
            "id": "selection",
            "name": "Selection",
            "templateHash": "a" * 64,
            "families": [
                {"id": "compact", "name": "Compact"},
                {"id": "spacious", "name": "Spacious"},
            ],
            "storyRecipe": {
                "document": [],
                "finding": [
                    {
                        "id": "overview",
                        "role": "finding-overview",
                        "repeat": "once",
                        "when": "has-data",
                        "familyId": "spacious",
                    }
                ],
                "appendix": [],
            },
            "layouts": [
                layout("compact-layout", "compact"),
                layout("spacious-layout", "spacious"),
            ],
        }
        report_ir = {
            "formatVersion": 2,
            "project": {},
            "presentation": {},
            "summary": {},
            "targets": [],
            "assets": [],
            "findings": [
                {
                    "id": "WEB-01-001",
                    "title": "Title longer than five characters",
                    "technical": {},
                    "procedure": {"steps": []},
                    "retests": [],
                }
            ],
        }
        family_plan = build_render_plan(report_ir, profile)
        self.assertEqual(family_plan["pages"][0]["layoutId"], "spacious-layout")

        automatic = deepcopy(profile)
        automatic["storyRecipe"]["finding"][0].pop("familyId")
        capacity_plan = build_render_plan(report_ir, automatic)
        self.assertEqual(capacity_plan["pages"][0]["layoutId"], "compact-layout")

        invalid = deepcopy(profile)
        invalid["storyRecipe"]["finding"][0]["familyId"] = "missing"
        with self.assertRaises(KitError) as error:
            validate_profile(invalid)
        self.assertEqual(error.exception.code, "PRESENTATION_RECIPE_FAMILY_INVALID")

    def test_story_recipe_auto_selects_variants_for_seven_steps_and_result(self) -> None:
        assets = [
            {"id": f"A-{index}", "source": f"evidence-{index}.png"}
            for index in range(1, 11)
        ]

        def usage(index: int) -> dict:
            return {"assetId": f"A-{index}", "placement": "inline", "order": index * 10}

        steps = []
        cursor = 1
        for number, count in enumerate((1, 1, 2, 2, 1, 1, 2), start=1):
            evidence = [usage(index) for index in range(cursor, cursor + count)]
            cursor += count
            steps.append(
                {
                    "id": f"STEP-{number:03d}",
                    "number": number,
                    "title": f"Step {number}",
                    "action": "Perform the action",
                    "evidence": evidence,
                }
            )

        def layout(
            layout_id: str,
            role: str,
            item_capacity: int,
            evidence_per_item: int,
        ) -> dict:
            bindings = {"title": {"kind": "text", "shapeId": 2}}
            if role == "finding-procedure":
                bindings = {
                    "items.0.summary": {
                        "kind": "text",
                        "shapeId": 2,
                        "maxChars": 1,
                    }
                }
                shape_id = 3
                for item_index in range(item_capacity):
                    bindings[f"items.{item_index}.stepTitle"] = {
                        "kind": "text",
                        "shapeId": shape_id,
                    }
                    shape_id += 1
                    for evidence_index in range(evidence_per_item):
                        bindings[f"items.{item_index}.evidence.{evidence_index}"] = {
                            "kind": "image",
                            "shapeId": shape_id,
                            "fit": "contain",
                        }
                        shape_id += 1
            else:
                for evidence_index in range(evidence_per_item):
                    bindings[f"evidence.{evidence_index}"] = {
                        "kind": "image",
                        "shapeId": 4 + evidence_index,
                        "fit": "contain",
                    }
            return {
                "id": layout_id,
                "familyId": "shared-finding",
                "role": role,
                "sourceSlide": 1,
                "composition": {"itemCapacity": item_capacity},
                "variant": {
                    "kind": "primary",
                    "textDensity": "regular",
                    "priority": 0,
                    "conditions": {},
                },
                "bindings": bindings,
            }

        profile = {
            "formatVersion": PROFILE_FORMAT_VERSION,
            "id": "auto",
            "name": "Automatic",
            "templateHash": "a" * 64,
            "families": [{"id": "shared-finding", "name": "Shared finding"}],
            "storyRecipe": {
                "document": [],
                "finding": [
                    {
                        "id": "procedure",
                        "role": "finding-procedure",
                        "repeat": "each-procedure-step",
                        "when": "has-data",
                    },
                    {
                        "id": "result",
                        "role": "finding-result",
                        "repeat": "once",
                        "when": "has-data",
                    },
                ],
                "appendix": [],
            },
            "layouts": [
                layout("procedure-two-up", "finding-procedure", 2, 1),
                layout("procedure-single-wide", "finding-procedure", 1, 2),
                layout("result-1", "finding-result", 1, 1),
            ],
        }
        report_ir = {
            "formatVersion": 2,
            "project": {},
            "presentation": {},
            "summary": {},
            "targets": [],
            "assets": assets,
            "findings": [
                {
                    "id": "WEB-01-001",
                    "title": "Finding",
                    "summary": "Final observed result",
                    "impact": "Impact",
                    "evidence": [usage(1)],
                    "technical": {},
                    "procedure": {"preconditions": "", "steps": steps},
                    "retests": [],
                }
            ],
        }
        normalized = validate_profile(profile)
        procedure_layouts = [
            item for item in normalized["layouts"] if item["role"] == "finding-procedure"
        ]
        self.assertTrue(procedure_layouts)
        for procedure_layout in procedure_layouts:
            self.assertIn("summary", procedure_layout["bindings"])
            self.assertNotIn("items.0.summary", procedure_layout["bindings"])
            self.assertNotIn("maxChars", procedure_layout["bindings"]["summary"])
            self.assertNotIn("textDensity", procedure_layout["variant"])
        plan = build_render_plan(report_ir, normalized)
        self.assertEqual(len(plan["pages"]), 6)
        self.assertEqual(
            [page["layoutId"] for page in plan["pages"][:5]],
            [
                "procedure-two-up",
                "procedure-single-wide",
                "procedure-single-wide",
                "procedure-two-up",
                "procedure-single-wide",
            ],
        )
        self.assertEqual(
            [len(page["blocks"]) for page in plan["pages"][:5]],
            [2, 1, 1, 2, 1],
        )
        self.assertEqual(
            [[block["id"] for block in page["blocks"]] for page in plan["pages"][:5]],
            [
                ["STEP-001", "STEP-002"],
                ["STEP-003"],
                ["STEP-004"],
                ["STEP-005", "STEP-006"],
                ["STEP-007"],
            ],
        )
        self.assertEqual(plan["pages"][-1]["role"], "finding-result")
        self.assertEqual(plan["pages"][-1]["layoutId"], "result-1")
        self.assertEqual(
            {page["selection"]["familyId"] for page in plan["pages"]},
            {"shared-finding"},
        )
        self.assertEqual(
            plan["pages"][0]["blocks"][0]["evidence"][0]["id"],
            plan["pages"][-1]["evidence"][0]["id"],
        )

    def test_renderer_binds_two_procedure_steps_to_distinct_page_regions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            template = root / "template.pptx"
            output = root / "two-up.pptx"
            create_template(template)
            profile = {
                "formatVersion": PROFILE_FORMAT_VERSION,
                "id": "two-up",
                "name": "Two-up procedure",
                "templateHash": template_digest(template),
                "families": [{"id": "procedure", "name": "Procedure"}],
                "storyRecipe": {
                    "document": [],
                    "finding": [
                        {
                            "id": "procedure",
                            "role": "finding-procedure",
                            "repeat": "each-procedure-step",
                            "when": "has-data",
                        }
                    ],
                    "appendix": [],
                },
                "layouts": [
                    {
                        "id": "procedure-two-up",
                        "familyId": "procedure",
                        "role": "finding-procedure",
                        "sourceSlide": 1,
                        "composition": {"itemCapacity": 2},
                        "variant": {
                            "kind": "primary",
                            "textDensity": "regular",
                            "priority": 0,
                            "conditions": {},
                        },
                        "bindings": {
                            "items.0.stepNumber": {
                                "kind": "text",
                                "shapeId": 2,
                                "formatter": {
                                    "type": "sequence",
                                    "style": "decimal",
                                    "padding": 2,
                                    "prefix": "STEP ",
                                },
                            },
                            "items.1.stepNumber": {
                                "kind": "text",
                                "shapeId": 4,
                                "formatter": {
                                    "type": "sequence",
                                    "style": "decimal",
                                    "padding": 2,
                                    "prefix": "STEP ",
                                },
                            },
                        },
                    }
                ],
            }
            report_ir = {
                "formatVersion": 2,
                "project": {},
                "presentation": {},
                "summary": {},
                "targets": [],
                "assets": [],
                "findings": [
                    {
                        "id": "WEB-01-001",
                        "title": "Finding",
                        "evidence": [],
                        "technical": {},
                        "procedure": {
                            "steps": [
                                {"id": "STEP-001", "number": 1, "title": "STEP 1", "evidence": []},
                                {"id": "STEP-002", "number": 2, "title": "STEP 2", "evidence": []},
                            ]
                        },
                        "retests": [],
                    }
                ],
            }
            plan = build_render_plan(report_ir, profile)
            self.assertEqual(len(plan["pages"]), 1)
            self.assertEqual([block["id"] for block in plan["pages"][0]["blocks"]], ["STEP-001", "STEP-002"])
            render_presentation(template, profile, plan, output, project_root=root)
            with zipfile.ZipFile(output) as archive:
                slide_xml = archive.read("ppt/slides/slide1.xml").decode("utf-8")
            self.assertIn("STEP 01", slide_xml)
            self.assertIn("STEP 02", slide_xml)

    def test_procedure_overflow_uses_continuation_variant(self) -> None:
        profile = {
            "formatVersion": 3,
            "id": "overflow",
            "name": "Overflow",
            "templateHash": "a" * 64,
            "families": [{"id": "procedure", "name": "Procedure"}],
            "storyRecipe": {
                "document": [],
                "finding": [
                    {
                        "id": "procedure",
                        "role": "finding-procedure",
                        "repeat": "each-procedure-step",
                        "when": "has-data",
                    }
                ],
                "appendix": [],
            },
            "layouts": [
                {
                    "id": "primary",
                    "familyId": "procedure",
                    "role": "finding-procedure",
                    "sourceSlide": 1,
                    "variant": {"kind": "primary", "textDensity": "regular", "priority": 0, "conditions": {}},
                    "bindings": {
                        "stepTitle": {"kind": "text", "shapeId": 2},
                        "evidence.0": {"kind": "image", "shapeId": 4},
                        "evidence.1": {"kind": "image", "shapeId": 5},
                    },
                },
                {
                    "id": "continuation",
                    "familyId": "procedure",
                    "role": "finding-procedure",
                    "sourceSlide": 1,
                    "variant": {"kind": "continuation", "textDensity": "regular", "priority": 0, "conditions": {}},
                    "bindings": {
                        "page": {"kind": "text", "shapeId": 2},
                        "evidence.0": {"kind": "image", "shapeId": 4},
                        "evidence.1": {"kind": "image", "shapeId": 5},
                    },
                },
            ],
        }
        assets = [{"id": f"A-{index}", "source": f"{index}.png"} for index in range(5)]
        report_ir = {
            "formatVersion": 2,
            "project": {},
            "summary": {},
            "targets": [],
            "assets": assets,
            "findings": [
                {
                    "id": "WEB-01-001",
                    "title": "Finding",
                    "evidence": [],
                    "technical": {},
                    "procedure": {
                        "steps": [
                            {
                                "id": "STEP-001",
                                "number": 1,
                                "title": "Step",
                                "evidence": [
                                    {"assetId": item["id"], "placement": "inline"}
                                    for item in assets
                                ],
                            }
                        ]
                    },
                    "retests": [],
                }
            ],
        }
        plan = build_render_plan(report_ir, profile)
        self.assertEqual(len(plan["pages"]), 3)
        self.assertEqual(
            [page["selection"]["variantKind"] for page in plan["pages"]],
            ["primary", "continuation", "continuation"],
        )
        self.assertEqual(
            [len(page["blocks"][0]["evidence"]) for page in plan["pages"]],
            [2, 2, 1],
        )

    def test_appendix_and_attachment_usage_are_separated(self) -> None:
        profile = {
            "formatVersion": 3,
            "id": "appendix",
            "name": "Appendix",
            "templateHash": "a" * 64,
            "families": [{"id": "appendix", "name": "Appendix"}],
            "storyRecipe": {
                "document": [],
                "finding": [],
                "appendix": [
                    {
                        "id": "appendix",
                        "role": "evidence-appendix",
                        "repeat": "evidence-pages",
                        "when": "has-data",
                    }
                ],
            },
            "layouts": [
                {
                    "id": "appendix-one",
                    "familyId": "appendix",
                    "role": "evidence-appendix",
                    "sourceSlide": 1,
                    "variant": {"kind": "primary", "textDensity": "regular", "priority": 0, "conditions": {}},
                    "bindings": {"evidence.0": {"kind": "image", "shapeId": 4}},
                }
            ],
        }
        report_ir = {
            "formatVersion": 2,
            "project": {},
            "summary": {},
            "targets": [],
            "assets": [
                {"id": "APP", "source": "appendix.png"},
                {"id": "ATT", "source": "request.http"},
            ],
            "findings": [
                {
                    "id": "WEB-01-001",
                    "title": "Finding",
                    "evidence": [
                        {"assetId": "APP", "placement": "appendix"},
                        {"assetId": "ATT", "placement": "attachment", "caption": "Raw request"},
                    ],
                    "technical": {},
                    "procedure": {"steps": []},
                    "retests": [],
                }
            ],
        }
        plan = build_render_plan(report_ir, profile)
        self.assertEqual(len(plan["pages"]), 1)
        self.assertEqual(plan["pages"][0]["role"], "evidence-appendix")
        self.assertEqual(plan["attachments"][0]["assetId"], "ATT")

    def test_output_and_manifest_commit_rolls_back_together(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "report.pptx"
            manifest = output.with_suffix(".pptx.manifest.json")
            staged = root / "staged.pptx"
            output.write_bytes(b"old-pptx")
            manifest.write_text("old-manifest", encoding="utf-8")
            staged.write_bytes(b"new-pptx")
            real_replace = renderer_module.os.replace

            def fail_manifest(source, destination):
                source_path = Path(source)
                if Path(destination) == manifest and source_path.suffix == ".tmp":
                    raise OSError("manifest commit failed")
                return real_replace(source, destination)

            with mock.patch.object(renderer_module.os, "replace", side_effect=fail_manifest):
                with self.assertRaisesRegex(OSError, "manifest commit failed"):
                    renderer_module._commit_output_pair(
                        staged,
                        output,
                        {"formatVersion": 1},
                    )
            self.assertEqual(output.read_bytes(), b"old-pptx")
            self.assertEqual(manifest.read_text(encoding="utf-8"), "old-manifest")

    def test_analyze_plan_render_and_validate_pptx(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            template = root / "template.pptx"
            create_template(template)
            image = root / "evidence.png"
            image.write_bytes(PNG_1X1)
            analysis = analyze_template(template)
            self.assertEqual(analysis["template"]["slideCount"], 1)
            self.assertEqual([item["id"] for item in analysis["slides"][0]["shapes"]], [2, 3, 4])
            report_ir = {
                "formatVersion": 2,
                "project": {},
                "summary": {},
                "targets": [],
                "assets": [
                    {
                        "id": "WEB-01-001:EVD-001",
                        "source": "evidence.png",
                        "type": "screenshot",
                    }
                ],
                "findings": [
                    {
                        "id": "WEB-01-001",
                        "title": "Rendered finding title",
                        "evidence": [
                            {"assetId": "WEB-01-001:EVD-001", "placement": "inline"}
                        ],
                        "procedure": {"steps": []},
                        "technical": {},
                        "retests": [],
                    }
                ],
            }
            profile = profile_for(template)
            plan = build_render_plan(report_ir, profile)
            self.assertEqual(len(plan["pages"]), 1)
            output = root / "report.pptx"
            render_presentation(
                template,
                profile,
                plan,
                output,
                project_root=root,
            )
            self.assertTrue(output.is_file())
            self.assertTrue(output.with_suffix(".pptx.manifest.json").is_file())
            self.assertEqual(validate_pptx(output)["slideCount"], 1)
            with zipfile.ZipFile(output, "r") as archive:
                content_types = archive.read("[Content_Types].xml").decode("utf-8")
                self.assertIn('<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">', content_types)
                self.assertNotIn("ns0:Types", content_types)
                slide = archive.read("ppt/slides/slide1.xml").decode("utf-8")
                self.assertIn("Rendered finding title", slide)
                self.assertNotIn("Evidence image", slide)
                rels = archive.read("ppt/slides/_rels/slide1.xml.rels").decode("utf-8")
                self.assertIn("otter-0001-evidence-0.png", rels)

    def test_renderer_removes_empty_optional_image_frame(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            template = root / "template.pptx"
            create_template(template)
            report_ir = {
                "formatVersion": 2,
                "project": {},
                "summary": {},
                "targets": [],
                "assets": [],
                "findings": [
                    {
                        "id": "WEB-01-001",
                        "title": "Finding without evidence",
                        "evidence": [],
                        "procedure": {"steps": []},
                        "technical": {},
                        "retests": [],
                    }
                ],
            }
            profile = profile_for(template)
            plan = build_render_plan(report_ir, profile)
            output = root / "report.pptx"
            render_presentation(template, profile, plan, output, project_root=root)

            with zipfile.ZipFile(output, "r") as archive:
                slide = archive.read("ppt/slides/slide1.xml").decode("utf-8")
            self.assertNotIn('id="4" name="Evidence frame"', slide)
            self.assertNotIn("Evidence image", slide)

    def test_project_service_builds_semantic_ir_plan_and_pptx(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            service = ProjectService.create_project(root / "project", "DEMO-WEB", "Demo")
            service.create_target("WEB-01", "Portal", "https://example.test")
            finding = service.create_finding(
                FindingInput(
                    target_id="WEB-01",
                    title="Service finding",
                    template_id="W-05",
                    template_version=1,
                )
            )
            service.update_finding(
                finding.id,
                status="Confirmed",
                summary="Summary",
                result_summary="The vulnerable behavior was reproduced and verified.",
                impact="Impact",
                remediation="Remediation",
            )
            evidence_file = root / "source.png"
            evidence_file.write_bytes(PNG_1X1)
            service.add_evidence(
                finding.id,
                evidence_file,
                "Screenshot",
                classification="report-ready",
                use_in_finding=True,
            )
            template = root / "template.pptx"
            create_template(template)
            profile_path = root / "profile.json"
            profile_path.write_text(
                json.dumps(profile_for(template), ensure_ascii=False), encoding="utf-8"
            )
            report_ir = service.build_presentation_ir()
            self.assertEqual(report_ir["formatVersion"], 2)
            finding_values = report_ir["findings"][0]
            self.assertEqual(
                finding_values["resultSummary"],
                "The vulnerable behavior was reproduced and verified.",
            )
            self.assertEqual(finding_values["findingId"], finding.id)
            self.assertEqual(finding_values["findingNumber"], 1)
            self.assertEqual(finding_values["findingCode"], "W-05")
            self.assertEqual(report_ir["findings"][0]["evidence"][0]["assetId"], "WEB-01-001:EVD-001")
            plan_path = root / "plan.json"
            plan = service.create_presentation_plan(profile_path, plan_path)
            self.assertEqual(len(plan["pages"]), 1)
            self.assertEqual(
                plan["pages"][0]["values"]["resultSummary"],
                "The vulnerable behavior was reproduced and verified.",
            )
            self.assertTrue(
                service.presentation_plan_status(
                    profile_path, plan_path, template_path=template
                )["isCurrent"]
            )
            output = service.render_presentation(
                template,
                profile_path,
                root / "service.pptx",
                plan_path=plan_path,
            )
            self.assertTrue(output.is_file())
            self.assertEqual(validate_pptx(output)["slideCount"], 1)
            service.update_finding(finding.id, summary="Changed after planning")
            status = service.presentation_plan_status(
                profile_path, plan_path, template_path=template
            )
            self.assertFalse(status["isCurrent"])
            self.assertEqual(status["changed"], ["project"])
            with self.assertRaisesRegex(Exception, "보고서 데이터가 변경"):
                service.render_presentation(
                    template,
                    profile_path,
                    root / "stale.pptx",
                    plan_path=plan_path,
                )

    def test_plan_merge_resets_order_only_when_semantic_page_set_changes(self) -> None:
        def page(key: str, role: str, layout_id: str) -> dict:
            return {
                "id": f"page-{key}",
                "semanticKey": key,
                "role": role,
                "layoutId": layout_id,
                "included": True,
                "values": {},
                "evidence": [],
                "overrides": {},
            }

        common = {
            "formatVersion": 2,
            "templateHash": "a" * 64,
            "reportIrHash": "b" * 64,
            "profileHash": "c" * 64,
            "warnings": [],
            "attachments": [],
        }
        profile = {
            "layouts": [
                {"id": "procedure", "role": "finding-procedure"},
                {"id": "result", "role": "finding-result"},
            ]
        }
        generated = {
            **common,
            "pages": [
                page("finding:1:procedure:new-group", "finding-procedure", "procedure"),
                page("finding:1:result", "finding-result", "result"),
            ],
        }
        previous = {
            **common,
            "pages": [
                {
                    **page("finding:1:result", "finding-result", "result"),
                    "included": False,
                    "overrides": {"evidence.0": {"fit": "contain"}},
                },
                page("finding:1:procedure:old-step", "finding-procedure", "procedure"),
            ],
        }
        merged = ProjectService._merge_presentation_plan(
            previous,
            deepcopy(generated),
            profile,
        )
        self.assertEqual(
            [item["semanticKey"] for item in merged["pages"]],
            ["finding:1:procedure:new-group", "finding:1:result"],
        )
        self.assertFalse(merged["pages"][1]["included"])
        self.assertEqual(
            merged["pages"][1]["overrides"], {"evidence.0": {"fit": "contain"}}
        )

        same_pages = {
            **common,
            "pages": [
                {
                    **page("finding:1:result", "finding-result", "result"),
                    "included": False,
                },
                page(
                    "finding:1:procedure:new-group",
                    "finding-procedure",
                    "procedure",
                ),
            ],
        }
        preserved = ProjectService._merge_presentation_plan(
            same_pages,
            deepcopy(generated),
            profile,
        )
        self.assertEqual(
            [item["semanticKey"] for item in preserved["pages"]],
            ["finding:1:result", "finding:1:procedure:new-group"],
        )

    def test_project_service_scopes_plan_and_render_to_selected_targets(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            service = ProjectService.create_project(root / "project", "SCOPE-WEB", "Scope")
            service.create_target("WEB-01", "Included", "https://included.test")
            service.create_target("WEB-02", "Excluded", "https://excluded.test")
            included = service.create_finding(
                FindingInput(target_id="WEB-01", title="Included finding")
            )
            excluded = service.create_finding(
                FindingInput(target_id="WEB-02", title="Excluded finding")
            )
            for finding in (included, excluded):
                service.update_finding(
                    finding.id,
                    status="Confirmed",
                    summary=f"Summary {finding.id}",
                    impact="Impact",
                    remediation="Remediation",
                )
            template = root / "template.pptx"
            create_template(template)
            profile_path = root / "profile.json"
            profile_path.write_text(
                json.dumps(profile_for(template), ensure_ascii=False), encoding="utf-8"
            )
            scope = {"mode": "selected-targets", "targetIds": ["WEB-01"]}
            report_ir = service.build_presentation_ir(scope=scope)
            self.assertEqual(report_ir["scope"], scope)
            self.assertEqual(report_ir["summary"]["targetCount"], 1)
            self.assertEqual([item["id"] for item in report_ir["targets"]], ["WEB-01"])
            self.assertEqual([item["id"] for item in report_ir["findings"]], [included.id])

            plan_path = root / "scoped-plan.json"
            plan = service.create_presentation_plan(
                profile_path,
                plan_path,
                scope=scope,
            )
            self.assertEqual(plan["scope"], scope)
            output = root / "scoped.pptx"
            service.render_presentation(
                template,
                profile_path,
                output,
                plan_path=plan_path,
            )
            with zipfile.ZipFile(output) as archive:
                slide_xml = "\n".join(
                    archive.read(name).decode("utf-8")
                    for name in archive.namelist()
                    if name.startswith("ppt/slides/slide") and name.endswith(".xml")
                )
            self.assertIn("Included finding", slide_xml)
            self.assertNotIn("Excluded finding", slide_xml)

            service.update_finding(excluded.id, summary="Changed outside selected scope")
            service.render_presentation(
                template,
                profile_path,
                root / "still-current.pptx",
                plan_path=plan_path,
            )
            service.update_finding(included.id, summary="Changed inside selected scope")
            with self.assertRaisesRegex(Exception, "보고서 데이터가 변경"):
                service.render_presentation(
                    template,
                    profile_path,
                    root / "stale-selected.pptx",
                    plan_path=plan_path,
                )


if __name__ == "__main__":
    unittest.main()
