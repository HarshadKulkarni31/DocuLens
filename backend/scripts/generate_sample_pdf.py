import os
from pathlib import Path
try:
    import pymupdf as fitz
except ImportError:
    import fitz

def create_sample_pdf(output_path: str):
    doc = fitz.open()

    # Page 1: Overview and Core Architecture
    page1 = doc.new_page()
    page1.insert_text(
        (50, 70),
        "SolarPulse Technical Whitepaper\n"
        "Next-Generation Renewable Grid Optimization & Storage\n\n"
        "1. Executive Summary\n"
        "Project SolarPulse is an intelligent grid energy management solution designed to balance\n"
        "intermittent photovoltaic power generation with municipal electrical demand. Utilizing\n"
        "advanced predictive load algorithms, SolarPulse achieves a peak round-trip efficiency of 94.2%.\n"
        "The primary battery chemistry utilizes high-density Lithium Iron Phosphate (LiFePO4) cells,\n"
        "chosen specifically for thermal stability, cycle longevity (exceeding 8,000 cycles at 80% DoD),\n"
        "and reduced supply-chain environmental impact.\n\n"
        "2. Core Architecture\n"
        "The power conversion system incorporates three bidirectional 500 kW Silicon Carbide (SiC)\n"
        "inverters capable of sub-10 millisecond grid-forming response during frequency fluctuations.\n"
        "Telemetry is processed through an edge compute gateway running an embedded Linux kernel.",
        fontsize=11,
    )

    # Page 2: Operational Parameters and Thermal Management
    page2 = doc.new_page()
    page2.insert_text(
        (50, 70),
        "SolarPulse Technical Whitepaper - Page 2\n\n"
        "3. Thermal Management & Environmental Specifications\n"
        "Battery thermal regulation is maintained via a Dual-loop Closed Glycol Cooling system.\n"
        "The system operates reliably across an ambient temperature range from -20°C to +55°C.\n"
        "Internal container temperature is actively maintained between 21°C and 25°C to preserve\n"
        "cell lifespan and prevent localized thermal runaway.\n\n"
        "4. Redundancy and Safety Mechanisms\n"
        "Each battery rack includes localized aerosol fire suppression (Stat-X aerosol generators)\n"
        "integrated with multi-spectrum optical flame and hydrogen gas detectors. If gas concentration\n"
        "exceeds 15% of the lower explosive limit (LEL), high-velocity exhaust fans activate\n"
        "and isolate the affected battery rack within 250 milliseconds.",
        fontsize=11,
    )

    # Page 3: Financial Projections and ROI
    page3 = doc.new_page()
    page3.insert_text(
        (50, 70),
        "SolarPulse Technical Whitepaper - Page 3\n\n"
        "5. Financial Analysis & Capital Investment\n"
        "The initial capital expenditure (CapEx) for the baseline 2.0 MW / 8.0 MWh installation is $14.8 million.\n"
        "Operating expenses (OpEx) are modeled at $210,000 annually, covering preventative maintenance,\n"
        "remote monitoring, and insurance.\n\n"
        "6. Return on Investment (ROI)\n"
        "Projected annual cost savings and grid arbitrage revenue equal $4.2 million per year.\n"
        "Based on discounted cash flow modeling with an 8% discount rate, the estimated payback period\n"
        "is calculated at 3.8 years. The total 20-year net present value (NPV) is estimated at $22.6 million.",
        fontsize=11,
    )

    # Page 4: Regulatory Compliance and Certification
    page4 = doc.new_page()
    page4.insert_text(
        (50, 70),
        "SolarPulse Technical Whitepaper - Page 4\n\n"
        "7. Regulatory Compliance and Industry Standards\n"
        "SolarPulse complies with all relevant national and international grid interconnection standards:\n"
        "- IEEE 1547-2018: Standard for Interconnection and Interoperability of Distributed Energy Resources\n"
        "- UL 9540A: Test Method for Evaluating Thermal Runaway Fire Propagation in Battery Systems\n"
        "- ISO 14001: Environmental Management Systems Certification\n"
        "- NFPA 855: Standard for the Installation of Stationary Energy Storage Systems\n\n"
        "8. Limitations and Exclusions\n"
        "The baseline deployment does not support extreme sub-zero operation below -30°C without the auxiliary\n"
        "Arctic Heating Package. Furthermore, black-start capabilities require optional microgrid sync modules.",
        fontsize=11,
    )

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    doc.save(output_path)
    doc.close()
    print(f"Sample PDF successfully generated at: {output_path}")

if __name__ == "__main__":
    out_dir = Path(__file__).resolve().parent.parent.parent / "sample_documents"
    pdf_file = out_dir / "solarpulse_technical_report.pdf"
    create_sample_pdf(str(pdf_file))

