"""Package checked report/source/PPTX; never transmit or operate hardware."""
from pathlib import Path
import hashlib,json,re,shutil,zipfile
from datetime import datetime,timezone
from pypdf import PdfReader

repo=Path('.').resolve();unit=repo.parent;source=repo/'outputs/report/iccp_draft_20261103_01'
presentation=repo/'outputs/presentation/talk_updated_20261103_05/MECH5720_scanner_results_for_team.pptx'
pdf=unit/'output/pdf/MECH5720_Major_Project_Draft_20261103.pdf'
bundle=unit/'output/MECH5720_Major_Project_Overleaf_Draft_20261103.zip'
download=Path('C:/Users/buzza/Downloads/MECH5720_Scanner_Results_20261103_v05.pptx')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
assert not pdf.exists() and not bundle.exists() and not download.exists(),'Versioned outputs already exist; inspect rather than overwrite'
r=PdfReader(source/'main.pdf');assert len(r.pages)==6
text='\n'.join(p.extract_text() or '' for p in r.pages)
assert 'REFERENCES' in text and '[PENDING G1' in text and 'G5' in text
log=(source/'main.log').read_text(errors='replace')
assert not any(s in log for s in ['Overfull','LaTeX Warning:','LaTeX Font Warning:','undefined references'])
template=zipfile.ZipFile(source/'template_original/5720_Project_Report.zip')
assert (source/'IEEEtran.cls').read_bytes()==template.read('IEEEtran.cls')
pptcheck=json.loads((repo/'outputs/presentation/talk_complete_build/final.validation.json').read_text())
assert pptcheck['packageIntegrity']['status']=='pass' and pptcheck['presentationLayout']['findingCount']==0
notes=json.loads((repo/'outputs/presentation/talk_complete_build/speaker_notes.json').read_text())
assert len(notes)==14 and sum(int(re.search(r'\[(\d+) seconds\]',q['notes']).group(1)) for q in notes[:10])==300
cov=json.loads((source/'regenerated_key_figure/coverage.json').read_text())
assert [(q['unique_covered_bins'],q['fixed_mask_pixels']) for q in cov]==[(939,13715),(478,13715)]
pdf.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source/'main.pdf',pdf);shutil.copy2(presentation,download)
manifest=dict(created_utc=datetime.now(timezone.utc).isoformat(),report_pages_total=6,body_page_limit_satisfied=True,
    source_template='Downloads/5720_Project_Report.zip',template_sha256=sha(source/'template_original/5720_Project_Report.zip'),unchanged_IEEEtran_cls=True,
    compiled_with='Official SHA256-verified Tectonic0.17.0 WindowsMSVC; no system installation change',
    latex_warnings=[],all_pdf_pages_rendered_and_visually_reviewed=6,
    presentation_main_slides=10,presentation_backup_slides=4,main_talk_seconds=300,all_final_slides_visually_reviewed=14,
    report_pdf=dict(path=str(pdf),sha256=sha(pdf)),presentation=dict(path=str(presentation),download_copy=str(download),sha256=sha(presentation)),
    verified_key_figure_results=cov,focused_tests='8passed; no full-suite claim',
    whatsapp=dict(authorized=True,recipient_requested='MECH57/MECH5720 group',caption_requested=None,sent=False,
        blocker='Local browser use is disabled in Work settings; reported again after user said enabled. No upload or message was attempted.'),
    overleaf=dict(live_project_changed=False,downloaded_template_used=True,source_package=str(bundle)),
    no_hardware_operation=True,no_git_publish_or_visibility_change=True)
(source/'DELIVERY_MANIFEST.json').write_text(json.dumps(manifest,indent=2))
root_files=['main.tex','references.bib','IEEEtran.cls','README.md','EVIDENCE_AUDIT.md','PENDING_ACTIONS.md','regenerate_key_figure.py','DELIVERY_MANIFEST.json']
with zipfile.ZipFile(bundle,'x',compression=zipfile.ZIP_DEFLATED) as z:
    for name in root_files:z.write(source/name,name)
    for directory in ['figures','evidence','template_original','repro_data']:
        for p in sorted((source/directory).rglob('*')):
            if p.is_file():z.write(p,p.relative_to(source).as_posix())
    z.write(pdf,'MECH5720_Major_Project_Draft.pdf')
with zipfile.ZipFile(bundle) as z:assert z.testzip() is None and 'main.tex' in z.namelist() and not any('.runtime' in n for n in z.namelist())
receipt=repo/'outputs/report/DELIVERY_20261103.json';receipt.write_text(json.dumps({**manifest,'source_zip_sha256':sha(bundle),'source_zip_bytes':bundle.stat().st_size},indent=2))
h=repo/'PROJECT_HANDOFF_CURRENT.md';prior=h.read_text(encoding='utf-8');prefix='NEWEST report/presentation delivery3Nov: PPTXv05 outputs/presentation/talk_updated_20261103_05/MECH5720_scanner_results_for_team.pptx and identical Downloads/MECH5720_Scanner_Results_20261103_v05.pptx.10main/300s+4backup; ND+coverage included;14renderedslideschecked, package/layout/nativechart/table checks passed. Report uses downloaded5720_Project_Report.zip unchangedIEEEtran.cls; local source outputs/report/iccp_draft_20261103_01, finalPDF ../output/pdf/MECH5720_Major_Project_Draft_20261103.pdf (6totalpages inclrefs, noLaTeXwarnings, all6visuallychecked), sourceZIP ../output/MECH5720_Major_Project_Overleaf_Draft_20261103.zip. Contains proposal/lab evidenceaudit, pending G1--G5, minimalcoveragegenerator verified,8focusedtests passed. IMPORTANT WHATSAPP SEND NOT DONE: user explicitly authorised PPTX-only attachment/no caption toMECH57group, but browser tool repeatedlyreports localbrowser disabled evenafteruser enabled; no upload/message attempted. Overleafliveproject NOTedited; downloadedtemplateused. Pending: independentgeometry,true3Dcompleteness,calibratedND,build/repoverification aswellascontinuous/speed. No hardware operated in reportturn. LatestNDphysicalstate remainsinstalled/laser-off fromprevioushandoff.\n\n'
if not prior.startswith(prefix):h.write_text(prefix+prior,encoding='utf-8')
print(json.dumps(dict(pdf=str(pdf),source_zip=str(bundle),pptx=str(presentation),download_copy=str(download),whatsapp_sent=False),indent=2))
