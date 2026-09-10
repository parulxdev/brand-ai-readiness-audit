import os
import sys
import json
import subprocess

# Define the list of target client domains to audit
ENTERPRISE_TEST_DOMAINS = [
    # --- E-COMMERCE & RETAIL ---
    "https://www.nike.com",
    "https://www.walmart.com",
    "https://www.target.com",
    "https://www.homedepot.com",
    "https://www.bestbuy.com",
    "https://www.wayfair.com",
    "https://www.macys.com",
    "https://www.sephora.com",
    "https://www.nordstrom.com",
    "https://www.ikea.com",
    "https://www.adidas.com",
    "https://www.costco.com",

    # --- BANKING & FINANCIAL SERVICES ---
    "https://www.jpmorgan.com",
    "https://www.chase.com",
    "https://www.bankofamerica.com",
    "https://www.wellsfargo.com",
    "https://www.citi.com",
    "https://www.capitalone.com",
    "https://www.americanexpress.com",
    "https://www.goldmansachs.com",
    "https://www.hsbc.com",
    "https://www.barclays.com",
    "https://www.visa.com",
    "https://www.mastercard.com",

    # --- TECHNOLOGY & SOFTWARE ---
    "https://www.apple.com",
    "https://www.microsoft.com",
    "https://www.ibm.com",
    "https://www.oracle.com",
    "https://www.sap.com",
    "https://www.salesforce.com",
    "https://www.servicenow.com",
    "https://www.cisco.com",
    "https://www.autodesk.com",
    "https://www.intel.com",
    "https://www.dell.com",
    "https://www.hp.com",

    # --- TELECOMMUNICATIONS ---
    "https://www.verizon.com",
    "https://www.att.com",
    "https://www.t-mobile.com",
    "https://www.comcast.com",
    "https://www.vodafone.com",
    "https://www.orange.com",
    "https://www.telefonica.com",

    # --- TRAVEL & AIRLINES ---
    "https://www.delta.com",
    "https://www.united.com",
    "https://www.aa.com",
    "https://www.southwest.com",
    "https://www.emirates.com",
    "https://www.qatarairways.com",
    "https://www.singaporeair.com",
    "https://www.airindia.com",

    # --- HOSPITALITY ---
    "https://www.marriott.com",
    "https://www.hilton.com",
    "https://www.hyatt.com",
    "https://www.ihg.com",
    "https://www.accor.com",

    # --- MEDIA & ENTERTAINMENT ---
    "https://www.netflix.com",
    "https://www.disney.com",
    "https://www.sony.com",
    "https://www.nbcuniversal.com",
    "https://www.wbd.com",
    "https://www.paramount.com",
    "https://www.peacocktv.com",

    # --- FOOD & CONSUMER BRANDS ---
    "https://www.coca-cola.com",
    "https://www.pepsico.com",
    "https://www.mcdonalds.com",
    "https://www.starbucks.com",
    "https://www.kfc.com",
    "https://www.pg.com",
    "https://www.unilever.com",
    "https://www.nestle.com",

    # --- AUTOMOTIVE ---
    "https://www.toyota.com",
    "https://www.ford.com",
    "https://www.gm.com",
    "https://www.bmw.com",
    "https://www.mercedes-benz.com",
    "https://www.hyundai.com",
    "https://www.volkswagen.com",
    "https://www.tesla.com",

    # --- HEALTHCARE & LIFE SCIENCES ---
    "https://www.cvshealth.com",
    "https://www.unitedhealthgroup.com",
    "https://www.pfizer.com",
    "https://www.merck.com",
    "https://www.medtronic.com",
    "https://www.gehealthcare.com",
    "https://www.jnj.com",
    "https://www.roche.com",
    "https://www.novartis.com",

    # --- INDUSTRIAL & MANUFACTURING ---
    "https://www.siemens.com",
    "https://www.honeywell.com",
    "https://www.ge.com",
    "https://www.3m.com",
    "https://www.bosch.com",
    "https://www.caterpillar.com",
    "https://www.abb.com",

    # --- PROFESSIONAL SERVICES ---
    "https://www.accenture.com",
    "https://www.deloitte.com",
    "https://www.pwc.com",
    "https://www.ey.com",
    "https://www.kpmg.com",
    "https://www.mckinsey.com",
    "https://www.bcg.com",

    # --- ENERGY & UTILITIES ---
    "https://www.shell.com",
    "https://www.bp.com",
    "https://www.chevron.com",
    "https://www.exxonmobil.com",
    "https://www.totalenergies.com",

    # --- REAL ESTATE ---
    "https://www.zillow.com",
    "https://www.realtor.com",
    "https://www.redfin.com",
    "https://www.cb.com",

    # --- EDUCATION ---
    "https://www.harvard.edu",
    "https://www.stanford.edu",
    "https://www.mit.edu",
    "https://www.coursera.org",
    "https://www.edx.org",

    # --- GOVERNMENT / PUBLIC-SECTOR TEST CASES ---
    "https://www.usa.gov",
    "https://www.gov.uk",
    "https://www.canada.ca",
    "https://www.australia.gov.au",

    # --- ADOBE ---
    "https://www.adobe.com"
]

OUTPUT_DIR = "client_audit_reports"
os.makedirs(OUTPUT_DIR, exist_ok=True)

print(f"Starting AI-Readiness Audit across {len(ENTERPRISE_TEST_DOMAINS)} target domains...\n")

for site in ENTERPRISE_TEST_DOMAINS:
    clean_name = site.replace("https://", "").replace("http://", "").replace("www.", "").replace("/", "_")
    output_path = os.path.join(OUTPUT_DIR, f"{clean_name}.json")
    
    print(f"Auditing: {site} ...")
    
    try:
        proc = subprocess.run(
            [sys.executable, "skills/audit-orchestrator/scripts/synthesize_report.py", site],
            capture_output=True,
            text=True,
            timeout=45
        )
        
        if proc.returncode == 0 and proc.stdout.strip():
            report_data = json.loads(proc.stdout)
            
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(report_data, f, indent=2)
                
            print(f"  [SUCCESS] Saved report: {output_path}")
            print(f"  Vertical: {report_data.get('vertical')}")
            print(f"  Total Findings: {report_data.get('summary', {}).get('total_findings', 0)}\n")
        else:
            print(f"  [FAILED] Audit failed for {site}: {proc.stderr}\n")
            
    except subprocess.TimeoutExpired:
        print(f"  [TIMEOUT] Timed out auditing {site}\n")
    except Exception as e:
        print(f"  [ERROR] {str(e)}\n")

print(f"Batch audit execution complete. Reports saved to ./{OUTPUT_DIR}/")