# FMS Live Surface - Workflow Architecture Document

**Document Version:** 1.0
**Date:** 2025-12-10
**Author:** GIS Architecture Team

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Overview](#system-overview)
3. [Existing Workflow Architecture](#existing-workflow-architecture)
4. [Proposed Workflow Architecture](#proposed-workflow-architecture)
5. [Impact Analysis](#impact-analysis)
6. [Appendices](#appendices)

---

## Executive Summary

This document outlines the workflow architecture for the FMS (Fleet Management System) Live Surface data processing pipeline. FMS data from Minestar and Modular systems is consumed into MTD (Mine Technical Data) in WAIO (Western Australia Iron Ore). The document covers:

- **Existing Workflow**: End-to-end process from snippet file ingestion to mosaic dataset publication
- **Proposed Workflow**: Simplified architecture that generates raster/mosaic datasets for consumption by an existing publishing solution
- **Impact Analysis**: Assessment of changes, risks, and benefits

---

## System Overview

### Data Sources
| System | File Type | Description |
|--------|-----------|-------------|
| Minestar | `.snp` (Snippet) | Proprietary format containing x,y,z,datetime points |
| Modular | `.csv` | CSV files in WB94 or ER94 coordinate systems |

### Processing Volume
- ~18,000 snippet files per site per day
- Hourly processing cycles
- 5 mine sites processed in parallel

### Key Components
- **GIP (Global Integration Platform)**: File delivery to landing zones
- **Jenkins**: Job orchestration and scheduling
- **MTD Tools**: Raster/boundary generation and publishing
- **Enterprise Geodatabase**: Final mosaic dataset storage

---

## Existing Workflow Architecture

### High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                           EXISTING FMS LIVE SURFACE WORKFLOW                            │
└─────────────────────────────────────────────────────────────────────────────────────────┘

┌──────────────┐     ┌──────────────┐     ┌─────────────────────────────────────────────┐
│   MINESTAR   │     │   MODULAR    │     │                                             │
│   (Site)     │     │   (Site)     │     │              MINE SITES                     │
│              │     │              │     │   ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐       │
│  .snp files  │     │  .csv files  │     │   │ WB │ │ ER │ │ TG │ │ JB │ │ NM │       │
└──────┬───────┘     └──────┬───────┘     │   └────┘ └────┘ └────┘ └────┘ └────┘       │
       │                    │             └─────────────────────────────────────────────┘
       │                    │
       ▼                    ▼
┌─────────────────────────────────────────┐
│     GLOBAL INTEGRATION PLATFORM (GIP)   │
│                                         │
│  • Receives files from sites            │
│  • Drops files to GIS landing zones     │
│  • File delivery monitoring             │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│         FMS FILE LANDING ZONE           │
│                                         │
│  DEV:  <Path where FMS Uploads>         │
│  PROD: <Path where FMS Uploads>         │
│                                         │
│  ┌─────────────┐  ┌─────────────┐       │
│  │ .snp files  │  │ .csv files  │       │
│  │ (Minestar)  │  │ (Modular)   │       │
│  └─────────────┘  └─────────────┘       │
└────────────────┬────────────────────────┘
                 │
                 │ HOURLY TRIGGER
                 ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                        JENKINS MULTIJOB ORCHESTRATION                                   │
│                        (MTD - Hourly FMS)                                               │
│                                                                                         │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│   │                    PARALLEL EXECUTION (6 Jobs)                                  │  │
│   │                                                                                 │  │
│   │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │  │
│   │  │Monitoring│ │   WB     │ │   ER     │ │   TG     │ │   JB     │ │   NM     │ │  │
│   │  │   Job    │ │  Site    │ │  Site    │ │  Site    │ │  Site    │ │  Site    │ │  │
│   │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘ │  │
│   └─────────────────────────────────────────────────────────────────────────────────┘  │
└────────────────┬────────────────────────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              STEP 1: FILE CONVERSION                                    │
│                                                                                         │
│  ┌─────────────────────────────────┐    ┌─────────────────────────────────┐            │
│  │  FMS - Process Snippet Files    │    │  FMS - Process Modular CSV      │            │
│  │                                 │    │  Files                          │            │
│  │  • Parse .snp files             │    │  • Reproject WB94/ER94 → MGA50  │            │
│  │  • Extract x,y,z,datetime       │    │  • Filter points                │            │
│  │  • Reproject to MGA50           │    │  • Generate output CSV          │            │
│  │  • Filter noise/outliers        │    │                                 │            │
│  │  • Apply Z adjustment           │    │                                 │            │
│  │  • Generate CSV + JSON config   │    │                                 │            │
│  └────────────────┬────────────────┘    └────────────────┬────────────────┘            │
│                   │                                      │                             │
│                   └──────────────┬───────────────────────┘                             │
│                                  ▼                                                     │
│                   ┌──────────────────────────────┐                                     │
│                   │      STAGING FOLDER          │                                     │
│                   │  • CSV file (MGA50)          │                                     │
│                   │  • JSON config file          │                                     │
│                   └──────────────────────────────┘                                     │
└────────────────────────────────────────┬────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                         STEP 2: MTD PROCESS DATA - ELEVATION                            │
│                         (MRD - Elevation - Process Data)                                │
│                                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │                         RASTER GENERATION PIPELINE                              │   │
│  │                                                                                 │   │
│  │   ┌────────────┐    ┌────────────┐    ┌────────────┐    ┌────────────┐         │   │
│  │   │  CSV File  │───▶│ 3D Feature │───▶│    TIN     │───▶│   RASTER   │         │   │
│  │   │  (MGA50)   │    │   Class    │    │            │    │            │         │   │
│  │   └────────────┘    └────────────┘    └────────────┘    └────────────┘         │   │
│  │                                                                                 │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │                         BOUNDARY GENERATION                                     │   │
│  │                                                                                 │   │
│  │   • Generate boundary polygon from points                                       │   │
│  │   • Apply exclusion zone (MTD_Live_RoadsBuffered)                              │   │
│  │   • Clip raster to boundary                                                     │   │
│  │                                                                                 │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                         │
│  OUTPUT: Raster + Boundary stored in staging job folder                                │
└────────────────────────────────────────┬────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              STEP 3: MTD UPLOAD - ELEVATION                             │
│                                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │                                                                                 │   │
│  │   • Copy source files to published location (internal access only)              │   │
│  │   • Copy raster to published location                                           │   │
│  │   • Copy boundary to published location                                         │   │
│  │   • Clip raster based on boundary polygon                                       │   │
│  │                                                                                 │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                         │
│  PUBLISHED LOCATION: Internal network share                                            │
└────────────────────────────────────────┬────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                            STEP 4: MTD PUBLISH - ELEVATION                              │
│                                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │                                                                                 │   │
│  │   • Add Source Mosaic Dataset to Enterprise Geodatabase                         │   │
│  │   • Add to Derived Mosaic Dataset                                               │   │
│  │   • Update mosaic dataset metadata                                              │   │
│  │   • Mark job as published                                                       │   │
│  │                                                                                 │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                         │
│  TARGET: Enterprise Geodatabase (SDE) - MTD Mosaic Dataset                             │
└────────────────────────────────────────┬────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              STEP 5: CACHE UPDATE                                       │
│                              (MTD - FMS Cache Update Hourly)                            │
│                                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │                                                                                 │   │
│  │   • Refresh cached map service                                                  │   │
│  │   • Update service metadata                                                     │   │
│  │   • Notify dependent systems (Schedman)                                         │   │
│  │                                                                                 │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                         │
│  CONSUMERS: Schedman (Production Scheduling)                                           │
└─────────────────────────────────────────────────────────────────────────────────────────┘

                                    ┌─────────────┐
                                    │   NIGHTLY   │
                                    │   ARCHIVE   │
                                    └──────┬──────┘
                                           │
                                           ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              ARCHIVE PROCESS                                            │
│                              (FMS - Archive Snippet Files)                              │
│                                                                                         │
│   • Compress ~18k snippet files per site                                               │
│   • Move to archive folder: <path>                                                     │
│   • Clear landing zone                                                                 │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### Detailed Process Flow

#### Step 1: GIP File Delivery
```
┌─────────────────────────────────────────────────────────────────────────┐
│                     GIP FILE DELIVERY PROCESS                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   MINESTAR SITES                        MODULAR SITES                   │
│   ┌─────────────┐                       ┌─────────────┐                 │
│   │ Snippet     │                       │ CSV Files   │                 │
│   │ Files       │                       │ (WB94/ER94) │                 │
│   │ (.snp)      │                       │             │                 │
│   └──────┬──────┘                       └──────┬──────┘                 │
│          │                                     │                        │
│          ▼                                     ▼                        │
│   ┌─────────────────────────────────────────────────────────────────┐  │
│   │                    GIP SECURE TRANSFER                          │  │
│   │                                                                 │  │
│   │   • Encrypted file transfer from site                          │  │
│   │   • File integrity validation                                  │  │
│   │   • Delivery confirmation                                      │  │
│   │                                                                 │  │
│   └─────────────────────────────────────────────────────────────────┘  │
│          │                                     │                        │
│          ▼                                     ▼                        │
│   ┌─────────────────────────────────────────────────────────────────┐  │
│   │                    GIS LANDING ZONE                             │  │
│   │                                                                 │  │
│   │   DEV:  <Path where FMS Uploads>/                              │  │
│   │   PROD: <Path where FMS Uploads>/                              │  │
│   │                                                                 │  │
│   │   Structure:                                                    │  │
│   │   └── <site>/                                                   │  │
│   │       ├── snippet/                                              │  │
│   │       │   └── *.snp                                            │  │
│   │       └── csv/                                                  │  │
│   │           └── *.csv                                             │  │
│   │                                                                 │  │
│   └─────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

#### Step 2: Snippet File Conversion (Minestar)
```
┌─────────────────────────────────────────────────────────────────────────┐
│                   SNIPPET FILE CONVERSION PROCESS                       │
│                   (MinestarSnippetFileToCSV.py)                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   INPUT                                                                 │
│   ┌─────────────────────────────────────────────────────────────────┐  │
│   │  Snippet Files (.snp)                                           │  │
│   │  • Contains x,y,z,datetime points                               │  │
│   │  • Site-specific projection                                     │  │
│   └──────────────────────────────────────────────────────────────┬──┘  │
│                                                                   │     │
│   PROCESSING                                                      ▼     │
│   ┌─────────────────────────────────────────────────────────────────┐  │
│   │                                                                 │  │
│   │  1. PARSE SNIPPET FILES                                        │  │
│   │     • Read binary/text format                                  │  │
│   │     • Extract coordinates and timestamps                       │  │
│   │                                                                 │  │
│   │  2. Z ADJUSTMENT                                               │  │
│   │     • Apply zAdjustment value (e.g., 3.155 for WB/ER)         │  │
│   │     • Convert ADPH to AHD datum                                │  │
│   │                                                                 │  │
│   │  3. NOISE FILTERING                                            │  │
│   │     • Remove points without neighbors (MinNeighbours: 2)       │  │
│   │     • Filter Z values exceeding MaxZ (4000.0)                  │  │
│   │                                                                 │  │
│   │  4. DESPIKE                                                    │  │
│   │     • Run smoothing algorithm                                  │  │
│   │     • Adjust outlier points to tolerance                       │  │
│   │                                                                 │  │
│   │  5. REPROJECTION                                               │  │
│   │     • Convert from InputSpatialReference                       │  │
│   │     • Output to MGA50 (OutputSpatialReference)                 │  │
│   │                                                                 │  │
│   │  6. AOI FILTERING                                              │  │
│   │     • Filter points outside AOI polygon                        │  │
│   │     • Apply AOIWhere clause (e.g., MineSite='ER')             │  │
│   │                                                                 │  │
│   └─────────────────────────────────────────────────────────────────┘  │
│                                                                   │     │
│   OUTPUT                                                          ▼     │
│   ┌─────────────────────────────────────────────────────────────────┐  │
│   │  STAGING FOLDER                                                │  │
│   │  ├── output.csv (MGA50 coordinates)                            │  │
│   │  └── config.json (processing parameters)                       │  │
│   └─────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

#### Step 3: Raster Generation
```
┌─────────────────────────────────────────────────────────────────────────┐
│                    RASTER GENERATION PIPELINE                           │
│                    (MTD Process Data - Elevation)                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐      │
│   │   CSV    │────▶│ 3D Point │────▶│   TIN    │────▶│  RASTER  │      │
│   │   File   │     │ Feature  │     │          │     │          │      │
│   │  (MGA50) │     │  Class   │     │          │     │          │      │
│   └──────────┘     └──────────┘     └──────────┘     └──────────┘      │
│                                                                         │
│   PROCESS STEPS:                                                        │
│                                                                         │
│   1. CSV TO 3D FEATURE CLASS                                           │
│      ┌─────────────────────────────────────────────────────────────┐   │
│      │  • Import CSV coordinates                                   │   │
│      │  • Create 3D point geometry                                 │   │
│      │  • Set spatial reference to MGA50                           │   │
│      └─────────────────────────────────────────────────────────────┘   │
│                                                                         │
│   2. TIN CREATION                                                      │
│      ┌─────────────────────────────────────────────────────────────┐   │
│      │  • Generate Triangulated Irregular Network                  │   │
│      │  • Delaunay triangulation                                   │   │
│      │  • Surface interpolation                                    │   │
│      └─────────────────────────────────────────────────────────────┘   │
│                                                                         │
│   3. TIN TO RASTER                                                     │
│      ┌─────────────────────────────────────────────────────────────┐   │
│      │  • Convert TIN to elevation raster                          │   │
│      │  • Cell size: 2m (matches GridSize parameter)               │   │
│      │  • Output format: TIFF                                      │   │
│      └─────────────────────────────────────────────────────────────┘   │
│                                                                         │
│   4. BOUNDARY GENERATION                                               │
│      ┌─────────────────────────────────────────────────────────────┐   │
│      │  • Generate convex hull from points                         │   │
│      │  • Apply exclusion zone (MTD_Live_RoadsBuffered)           │   │
│      │  • Create boundary polygon                                  │   │
│      └─────────────────────────────────────────────────────────────┘   │
│                                                                         │
│   OUTPUT:                                                              │
│   ┌─────────────────────────────────────────────────────────────────┐  │
│   │  STAGING JOB FOLDER                                            │  │
│   │  ├── raster.tif                                                │  │
│   │  ├── boundary.shp                                              │  │
│   │  └── metadata.xml                                              │  │
│   └─────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

#### Step 4-5: Upload and Publish
```
┌─────────────────────────────────────────────────────────────────────────┐
│                    UPLOAD & PUBLISH WORKFLOW                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   MTD UPLOAD - ELEVATION                                               │
│   ┌─────────────────────────────────────────────────────────────────┐  │
│   │                                                                 │  │
│   │   STAGING                           PUBLISHED                   │  │
│   │   ┌─────────┐                      ┌─────────┐                 │  │
│   │   │ raster  │─────────────────────▶│ raster  │                 │  │
│   │   │ .tif    │      COPY &          │ .tif    │                 │  │
│   │   └─────────┘      CLIP            └─────────┘                 │  │
│   │   ┌─────────┐                      ┌─────────┐                 │  │
│   │   │boundary │─────────────────────▶│boundary │                 │  │
│   │   │ .shp    │                      │ .shp    │                 │  │
│   │   └─────────┘                      └─────────┘                 │  │
│   │   ┌─────────┐                      ┌─────────┐                 │  │
│   │   │ source  │─────────────────────▶│ source  │                 │  │
│   │   │ files   │                      │ files   │                 │  │
│   │   └─────────┘                      └─────────┘                 │  │
│   │                                                                 │  │
│   │   • Clip raster using boundary polygon                         │  │
│   │   • Internal access only                                       │  │
│   │                                                                 │  │
│   └─────────────────────────────────────────────────────────────────┘  │
│                                          │                              │
│                                          ▼                              │
│   MTD PUBLISH - ELEVATION                                              │
│   ┌─────────────────────────────────────────────────────────────────┐  │
│   │                                                                 │  │
│   │   PUBLISHED LOCATION               ENTERPRISE GEODATABASE      │  │
│   │   ┌─────────┐                      ┌─────────────────────┐     │  │
│   │   │ raster  │                      │  SOURCE MOSAIC      │     │  │
│   │   │ .tif    │─────────────────────▶│  DATASET            │     │  │
│   │   └─────────┘                      │                     │     │  │
│   │                                    │  • Add raster       │     │  │
│   │                                    │  • Update footprint │     │  │
│   │                                    │  • Set metadata     │     │  │
│   │                                    └──────────┬──────────┘     │  │
│   │                                               │                │  │
│   │                                               ▼                │  │
│   │                                    ┌─────────────────────┐     │  │
│   │                                    │  DERIVED MOSAIC     │     │  │
│   │                                    │  DATASET            │     │  │
│   │                                    │                     │     │  │
│   │                                    │  • Reference source │     │  │
│   │                                    │  • Apply functions  │     │  │
│   │                                    │  • Publish service  │     │  │
│   │                                    └─────────────────────┘     │  │
│   │                                                                 │  │
│   └─────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Monitoring Architecture
```
┌─────────────────────────────────────────────────────────────────────────┐
│                       MONITORING & ALERTING                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   SNIPPET FILE MONITORING (Hourly)                                     │
│   ┌─────────────────────────────────────────────────────────────────┐  │
│   │                                                                 │  │
│   │   ┌─────────────────┐                                          │  │
│   │   │  CHECK FILE     │                                          │  │
│   │   │  TIMESTAMPS     │                                          │  │
│   │   │                 │                                          │  │
│   │   │  Threshold:     │                                          │  │
│   │   │  10 minutes     │                                          │  │
│   │   └────────┬────────┘                                          │  │
│   │            │                                                    │  │
│   │            ▼                                                    │  │
│   │   ┌─────────────────┐         ┌─────────────────┐              │  │
│   │   │  FILES WITHIN   │   NO    │  TRIGGER ALERT  │              │  │
│   │   │  THRESHOLD?     │────────▶│                 │              │  │
│   │   └────────┬────────┘         │  • Email to GIP │              │  │
│   │            │ YES              │    (Jerome Green) │             │  │
│   │            ▼                  │  • Failover job  │              │  │
│   │   ┌─────────────────┐         │    triggered    │              │  │
│   │   │    CONTINUE     │         └─────────────────┘              │  │
│   │   │    PROCESSING   │                   │                      │  │
│   │   └─────────────────┘                   ▼                      │  │
│   │                              ┌─────────────────┐               │  │
│   │                              │  COPY FROM PROD │               │  │
│   │                              │  FILE SHARE     │               │  │
│   │                              └─────────────────┘               │  │
│   │                                                                 │  │
│   └─────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Jenkins Job Reference
```
┌─────────────────────────────────────────────────────────────────────────┐
│                         JENKINS JOBS REFERENCE                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   JOB NAME                              │ SCHEDULE  │ DESCRIPTION       │
│   ──────────────────────────────────────┼───────────┼──────────────────│
│   FMS - Process Snippet Files           │ Hourly    │ Convert .snp→CSV │
│   FMS - Process Modular CSV Files       │ Hourly    │ Reproject CSV    │
│   MTD - Hourly FMS                      │ Hourly    │ Main orchestrator│
│   MTD - FMS Cache Update Hourly         │ Hourly    │ Refresh cache    │
│   MTD - Live Surface Roads Update       │ Daily     │ Update exclusion │
│   MTD - Delete Hourly FMS               │ On-demand │ Cleanup utility  │
│   FMS - Archive Snippet Files           │ Nightly   │ Archive files    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Proposed Workflow Architecture

### Overview

The proposed solution simplifies the workflow by decoupling raster generation from direct SDE mosaic dataset publication. Instead of pushing directly to the SDE mosaic dataset, the new workflow will:

1. Generate raster/mosaic dataset outputs
2. Store outputs in a designated location
3. Leverage an **existing publishing solution** that accepts raster/mosaic dataset inputs

### High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                          PROPOSED FMS LIVE SURFACE WORKFLOW                             │
└─────────────────────────────────────────────────────────────────────────────────────────┘

┌──────────────┐     ┌──────────────┐
│   MINESTAR   │     │   MODULAR    │
│   (Site)     │     │   (Site)     │
│  .snp files  │     │  .csv files  │
└──────┬───────┘     └──────┬───────┘
       │                    │
       ▼                    ▼
┌─────────────────────────────────────────┐
│     GLOBAL INTEGRATION PLATFORM (GIP)   │
│     [NO CHANGE]                         │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│         FMS FILE LANDING ZONE           │
│         [NO CHANGE]                     │
└────────────────┬────────────────────────┘
                 │
                 │ HOURLY TRIGGER
                 ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                        JENKINS MULTIJOB ORCHESTRATION                                   │
│                        [MODIFIED - SIMPLIFIED PIPELINE]                                 │
│                                                                                         │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│   │                    PARALLEL EXECUTION (6 Jobs)                                  │  │
│   │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │  │
│   │  │Monitoring│ │   WB     │ │   ER     │ │   TG     │ │   JB     │ │   NM     │ │  │
│   │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘ │  │
│   └─────────────────────────────────────────────────────────────────────────────────┘  │
└────────────────┬────────────────────────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              STEP 1: FILE CONVERSION                                    │
│                              [NO CHANGE]                                                │
│                                                                                         │
│   • Parse snippet files / Reproject Modular CSV                                        │
│   • Output: CSV (MGA50) + JSON config                                                  │
│                                                                                         │
└────────────────────────────────────────┬────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                         STEP 2: MTD PROCESS DATA - ELEVATION                            │
│                         [MODIFIED - OUTPUT DESTINATION CHANGE]                          │
│                                                                                         │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│   │   CSV → 3D Feature Class → TIN → RASTER                                        │  │
│   │   + Boundary Generation                                                         │  │
│   │                                                                                 │  │
│   │   [SAME PROCESSING LOGIC]                                                       │  │
│   └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
│   OUTPUT CHANGE:                                                                        │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│   │                                                                                 │  │
│   │   EXISTING:  Store in staging → Upload → Publish to SDE                        │  │
│   │                                                                                 │  │
│   │   PROPOSED:  Store in OUTPUT FOLDER for External Publishing Solution           │  │
│   │                                                                                 │  │
│   │   OUTPUT FOLDER STRUCTURE:                                                      │  │
│   │   └── FMS_Output/                                                               │  │
│   │       └── <site>/                                                               │  │
│   │           └── <timestamp>/                                                      │  │
│   │               ├── raster.tif          (Elevation raster)                       │  │
│   │               ├── mosaic.gdb/         (Optional: File geodatabase mosaic)      │  │
│   │               ├── boundary.shp        (Boundary polygon)                       │  │
│   │               └── metadata.json       (Processing metadata)                    │  │
│   │                                                                                 │  │
│   └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
└────────────────────────────────────────┬────────────────────────────────────────────────┘
                                         │
                                         │  ┌─────────────────────────────────────────┐
                                         │  │         REMOVED STEPS                   │
                                         │  │                                         │
                                         │  │   ✗ MTD Upload - Elevation              │
                                         │  │   ✗ MTD Publish - Elevation             │
                                         │  │                                         │
                                         │  │   (Direct SDE publication removed)      │
                                         │  └─────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                         STEP 3: HANDOFF TO EXISTING PUBLISHING SOLUTION                 │
│                         [NEW - INTEGRATION POINT]                                       │
│                                                                                         │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│   │                                                                                 │  │
│   │   FMS WORKFLOW OUTPUT                    EXISTING PUBLISHING SOLUTION          │  │
│   │   ┌─────────────────────┐               ┌─────────────────────────────────┐    │  │
│   │   │                     │               │                                 │    │  │
│   │   │  • Raster (.tif)    │──────────────▶│  INPUT PARAMETERS:              │    │  │
│   │   │  • Mosaic Dataset   │               │  • Raster path                  │    │  │
│   │   │  • Boundary         │               │  • Mosaic dataset path          │    │  │
│   │   │  • Metadata         │               │  • Configuration                │    │  │
│   │   │                     │               │                                 │    │  │
│   │   └─────────────────────┘               │  PROCESS:                       │    │  │
│   │                                         │  • Validate input               │    │  │
│   │                                         │  • Add to SDE mosaic            │    │  │
│   │                                         │  • Update derived datasets      │    │  │
│   │                                         │  • Publish services             │    │  │
│   │                                         │                                 │    │  │
│   │                                         └─────────────────────────────────┘    │  │
│   │                                                                                 │  │
│   │   INTEGRATION OPTIONS:                                                         │  │
│   │   ┌─────────────────────────────────────────────────────────────────────────┐  │  │
│   │   │  Option A: Direct API/Function Call                                     │  │  │
│   │   │  • FMS job calls existing publishing solution directly                  │  │  │
│   │   │  • Pass raster/mosaic path as parameter                                 │  │  │
│   │   │                                                                         │  │  │
│   │   │  Option B: File-Based Trigger                                           │  │  │
│   │   │  • FMS job writes output + trigger file                                 │  │  │
│   │   │  • Publishing solution polls for new outputs                            │  │  │
│   │   │                                                                         │  │  │
│   │   │  Option C: Message Queue                                                │  │  │
│   │   │  • FMS job publishes message with output location                       │  │  │
│   │   │  • Publishing solution subscribes and processes                         │  │  │
│   │   └─────────────────────────────────────────────────────────────────────────┘  │  │
│   │                                                                                 │  │
│   └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
└────────────────────────────────────────┬────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                         STEP 4: EXISTING PUBLISHING SOLUTION                            │
│                         [EXISTING SYSTEM - NO CHANGE]                                   │
│                                                                                         │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│   │                                                                                 │  │
│   │   INPUTS (from FMS):                                                           │  │
│   │   • Raster file path                                                           │  │
│   │   • Mosaic dataset path (optional)                                             │  │
│   │   • Boundary polygon                                                           │  │
│   │   • Metadata/configuration                                                     │  │
│   │                                                                                 │  │
│   │   PROCESSING:                                                                  │  │
│   │   • Validate input raster/mosaic                                               │  │
│   │   • Add to enterprise geodatabase                                              │  │
│   │   • Update mosaic dataset                                                      │  │
│   │   • Rebuild overviews if needed                                                │  │
│   │   • Update map services                                                        │  │
│   │                                                                                 │  │
│   │   OUTPUT:                                                                      │  │
│   │   • Published to SDE mosaic dataset                                            │  │
│   │   • Services updated                                                           │  │
│   │                                                                                 │  │
│   └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
└────────────────────────────────────────┬────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              STEP 5: CACHE UPDATE                                       │
│                              [NO CHANGE]                                                │
│                                                                                         │
│   • MTD - FMS Cache Update Hourly                                                      │
│   • Refresh cached map service                                                         │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### Detailed Comparison: Existing vs Proposed

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                         WORKFLOW COMPARISON                                             │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                         │
│   EXISTING WORKFLOW                         PROPOSED WORKFLOW                           │
│   ─────────────────                         ─────────────────                           │
│                                                                                         │
│   ┌─────────────────────┐                   ┌─────────────────────┐                    │
│   │ 1. GIP Delivery     │                   │ 1. GIP Delivery     │  [SAME]           │
│   └──────────┬──────────┘                   └──────────┬──────────┘                    │
│              │                                         │                               │
│              ▼                                         ▼                               │
│   ┌─────────────────────┐                   ┌─────────────────────┐                    │
│   │ 2. File Conversion  │                   │ 2. File Conversion  │  [SAME]           │
│   │    (Snippet→CSV)    │                   │    (Snippet→CSV)    │                    │
│   └──────────┬──────────┘                   └──────────┬──────────┘                    │
│              │                                         │                               │
│              ▼                                         ▼                               │
│   ┌─────────────────────┐                   ┌─────────────────────┐                    │
│   │ 3. Process Data     │                   │ 3. Process Data     │  [SAME LOGIC]     │
│   │    (Generate Raster)│                   │    (Generate Raster)│                    │
│   └──────────┬──────────┘                   └──────────┬──────────┘                    │
│              │                                         │                               │
│              ▼                                         ▼                               │
│   ┌─────────────────────┐                   ┌─────────────────────┐                    │
│   │ 4. MTD Upload       │                   │ 4. OUTPUT TO FOLDER │  [MODIFIED]       │
│   │    (Copy to publish)│                   │    (Raster/Mosaic)  │                    │
│   └──────────┬──────────┘                   └──────────┬──────────┘                    │
│              │                                         │                               │
│              ▼                                         ▼                               │
│   ┌─────────────────────┐                   ┌─────────────────────┐                    │
│   │ 5. MTD Publish      │                   │ 5. EXISTING         │  [NEW INTEGRATION]│
│   │    (Add to SDE)     │                   │    PUBLISHING       │                    │
│   └──────────┬──────────┘                   │    SOLUTION         │                    │
│              │                              └──────────┬──────────┘                    │
│              │                                         │                               │
│              ▼                                         ▼                               │
│   ┌─────────────────────┐                   ┌─────────────────────┐                    │
│   │ 6. Cache Update     │                   │ 6. Cache Update     │  [SAME]           │
│   └─────────────────────┘                   └─────────────────────┘                    │
│                                                                                         │
│   COMPONENTS REMOVED:                       COMPONENTS ADDED:                          │
│   ───────────────────                       ────────────────                           │
│   • MTD Upload - Elevation                  • Output folder management                 │
│   • MTD Publish - Elevation                 • Integration layer/API call               │
│   • Direct SDE connection                   • Metadata JSON generation                 │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### Proposed Output Structure

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                         PROPOSED OUTPUT FOLDER STRUCTURE                                │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                         │
│   FMS_Output/                                                                          │
│   │                                                                                     │
│   ├── WB/                              (Whaleback site)                                │
│   │   ├── 20251210_0800/              (Timestamp folder)                               │
│   │   │   ├── WB_elevation.tif        (Elevation raster)                              │
│   │   │   ├── WB_boundary.shp         (Boundary polygon)                              │
│   │   │   ├── WB_boundary.dbf                                                          │
│   │   │   ├── WB_boundary.shx                                                          │
│   │   │   ├── WB_boundary.prj                                                          │
│   │   │   ├── metadata.json           (Processing metadata)                           │
│   │   │   └── ready.flag              (Trigger file for publishing)                   │
│   │   │                                                                                │
│   │   └── 20251210_0900/                                                               │
│   │       └── ...                                                                      │
│   │                                                                                     │
│   ├── ER/                              (Eastern Ridge site)                            │
│   │   └── ...                                                                          │
│   │                                                                                     │
│   ├── TG/                              (Tom Price site)                                │
│   │   └── ...                                                                          │
│   │                                                                                     │
│   ├── JB/                              (Jimblebar site)                                │
│   │   └── ...                                                                          │
│   │                                                                                     │
│   └── NM/                              (Newman site)                                   │
│       └── ...                                                                          │
│                                                                                         │
│   METADATA.JSON STRUCTURE:                                                             │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│   │   {                                                                             │  │
│   │     "site": "WB",                                                               │  │
│   │     "timestamp": "2025-12-10T08:00:00Z",                                        │  │
│   │     "sourceFiles": {                                                            │  │
│   │       "snippetCount": 1500,                                                     │  │
│   │       "csvCount": 0,                                                            │  │
│   │       "totalPoints": 82792,                                                     │  │
│   │       "validPoints": 82770                                                      │  │
│   │     },                                                                          │  │
│   │     "processing": {                                                             │  │
│   │       "zAdjustment": 3.155,                                                     │  │
│   │       "gridSize": 2,                                                            │  │
│   │       "maxZ": 4000.0,                                                           │  │
│   │       "spatialReference": "MGA50",                                              │  │
│   │       "despike": true                                                           │  │
│   │     },                                                                          │  │
│   │     "output": {                                                                 │  │
│   │       "rasterPath": "WB_elevation.tif",                                         │  │
│   │       "boundaryPath": "WB_boundary.shp",                                        │  │
│   │       "cellSize": 2,                                                            │  │
│   │       "format": "GeoTIFF"                                                       │  │
│   │     },                                                                          │  │
│   │     "status": "ready_for_publish"                                               │  │
│   │   }                                                                             │  │
│   └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### Integration Options Detail

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                         INTEGRATION OPTIONS                                             │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                         │
│   OPTION A: DIRECT API/FUNCTION CALL (RECOMMENDED)                                     │
│   ──────────────────────────────────────────────────                                   │
│                                                                                         │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│   │                                                                                 │  │
│   │   FMS Process Job                           Existing Publishing Solution       │  │
│   │   ┌─────────────────┐                      ┌─────────────────────────┐         │  │
│   │   │                 │                      │                         │         │  │
│   │   │  1. Generate    │    API/Function      │  publish_to_mosaic(     │         │  │
│   │   │     raster      │────────────────────▶ │    raster_path,         │         │  │
│   │   │                 │        Call          │    boundary_path,       │         │  │
│   │   │  2. Generate    │                      │    config               │         │  │
│   │   │     boundary    │                      │  )                      │         │  │
│   │   │                 │                      │                         │         │  │
│   │   │  3. Call API    │                      │                         │         │  │
│   │   │                 │◀────────────────────│  Return: success/fail   │         │  │
│   │   └─────────────────┘       Response       └─────────────────────────┘         │  │
│   │                                                                                 │  │
│   │   PROS:                              CONS:                                      │  │
│   │   • Immediate feedback               • Tighter coupling                         │  │
│   │   • Simpler error handling           • FMS job waits for completion            │  │
│   │   • Single transaction               • Requires API availability               │  │
│   │                                                                                 │  │
│   └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
│   OPTION B: FILE-BASED TRIGGER                                                         │
│   ────────────────────────────                                                         │
│                                                                                         │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│   │                                                                                 │  │
│   │   FMS Process Job              Output Folder            Publishing Solution    │  │
│   │   ┌─────────────┐             ┌─────────────┐          ┌─────────────────┐     │  │
│   │   │             │   Write     │             │   Poll   │                 │     │  │
│   │   │  Generate   │────────────▶│  raster.tif │◀─────────│  Watch folder   │     │  │
│   │   │  outputs    │             │  boundary   │          │  for ready.flag │     │  │
│   │   │             │             │  metadata   │          │                 │     │  │
│   │   │  Write      │────────────▶│  ready.flag │─────────▶│  Process &      │     │  │
│   │   │  trigger    │             │             │  Trigger │  publish        │     │  │
│   │   │             │             │             │          │                 │     │  │
│   │   └─────────────┘             └─────────────┘          └─────────────────┘     │  │
│   │                                                                                 │  │
│   │   PROS:                              CONS:                                      │  │
│   │   • Loose coupling                   • Delayed processing                       │  │
│   │   • FMS job completes quickly        • Complex error handling                   │  │
│   │   • Independent scaling              • File system dependency                   │  │
│   │                                                                                 │  │
│   └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
│   OPTION C: MESSAGE QUEUE                                                              │
│   ───────────────────────                                                              │
│                                                                                         │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│   │                                                                                 │  │
│   │   FMS Process Job        Message Queue          Publishing Solution            │  │
│   │   ┌─────────────┐       ┌─────────────┐        ┌─────────────────┐             │  │
│   │   │             │       │             │        │                 │             │  │
│   │   │  Generate   │       │   ┌─────┐   │        │   Subscribe     │             │  │
│   │   │  outputs    │──────▶│   │ MSG │   │───────▶│   & process     │             │  │
│   │   │             │ Pub   │   └─────┘   │  Sub   │                 │             │  │
│   │   │  Publish    │       │   ┌─────┐   │        │   Publish to    │             │  │
│   │   │  message    │       │   │ MSG │   │        │   SDE           │             │  │
│   │   │             │       │   └─────┘   │        │                 │             │  │
│   │   └─────────────┘       └─────────────┘        └─────────────────┘             │  │
│   │                                                                                 │  │
│   │   PROS:                              CONS:                                      │  │
│   │   • Highly decoupled                 • Additional infrastructure               │  │
│   │   • Reliable delivery                • More complex setup                       │  │
│   │   • Scalable                         • Operational overhead                     │  │
│   │                                                                                 │  │
│   └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Impact Analysis

### Summary Matrix

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              IMPACT ANALYSIS SUMMARY                                    │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                         │
│   CATEGORY          │ IMPACT   │ RISK    │ EFFORT  │ NOTES                             │
│   ──────────────────┼──────────┼─────────┼─────────┼─────────────────────────────────  │
│   Code Changes      │ MEDIUM   │ LOW     │ MEDIUM  │ Modify output logic only          │
│   Jenkins Jobs      │ MEDIUM   │ LOW     │ LOW     │ Simplify job chain                │
│   Infrastructure    │ LOW      │ LOW     │ LOW     │ No new infrastructure needed      │
│   Data Flow         │ MEDIUM   │ MEDIUM  │ LOW     │ New handoff point                 │
│   Dependencies      │ HIGH     │ MEDIUM  │ MEDIUM  │ Relies on existing solution       │
│   Testing           │ MEDIUM   │ MEDIUM  │ MEDIUM  │ Integration testing required      │
│   Rollback          │ LOW      │ LOW     │ LOW     │ Can revert to existing workflow   │
│   Performance       │ POSITIVE │ LOW     │ N/A     │ Potential improvement             │
│   Maintenance       │ POSITIVE │ LOW     │ N/A     │ Reduced complexity                │
│   Schedman Impact   │ LOW      │ LOW     │ LOW     │ No change to consumer interface   │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### Detailed Impact Assessment

#### 1. Code Changes Impact

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              CODE CHANGES IMPACT                                        │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                         │
│   AFFECTED COMPONENTS:                                                                 │
│                                                                                         │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│   │  COMPONENT                    │ CHANGE TYPE    │ COMPLEXITY │ FILES AFFECTED   │  │
│   │  ─────────────────────────────┼────────────────┼────────────┼─────────────────  │  │
│   │  MinestarSnippetFileToCSV.py  │ NO CHANGE      │ NONE       │ 0                │  │
│   │  MTD Process Data             │ MINOR MODIFY   │ LOW        │ 1-2              │  │
│   │  MTD Upload - Elevation       │ REMOVE/BYPASS  │ LOW        │ N/A              │  │
│   │  MTD Publish - Elevation      │ REMOVE/BYPASS  │ LOW        │ N/A              │  │
│   │  Output Handler (NEW)         │ NEW            │ MEDIUM     │ 1-2              │  │
│   │  Integration Layer (NEW)      │ NEW            │ MEDIUM     │ 1-3              │  │
│   └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
│   CHANGES REQUIRED:                                                                    │
│                                                                                         │
│   1. MTD Process Data - Elevation:                                                     │
│      • Modify output destination from staging → output folder                          │
│      • Add metadata.json generation                                                    │
│      • Add trigger file creation (if using file-based integration)                    │
│                                                                                         │
│   2. New Output Handler:                                                               │
│      • Create folder structure management                                              │
│      • Implement cleanup/archival of old outputs                                       │
│      • Generate standardized metadata                                                  │
│                                                                                         │
│   3. New Integration Layer:                                                            │
│      • Implement API call to existing publishing solution                              │
│      • Error handling and retry logic                                                  │
│      • Logging and monitoring                                                          │
│                                                                                         │
│   UNCHANGED:                                                                           │
│   • Snippet file parsing logic                                                         │
│   • CSV conversion and reprojection                                                    │
│   • Raster generation (TIN creation)                                                   │
│   • Boundary generation                                                                │
│   • Monitoring and alerting                                                            │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

#### 2. Jenkins Jobs Impact

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              JENKINS JOBS IMPACT                                        │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                         │
│   JOB STATUS MATRIX:                                                                   │
│                                                                                         │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│   │  JOB NAME                         │ STATUS     │ ACTION REQUIRED               │  │
│   │  ─────────────────────────────────┼────────────┼────────────────────────────── │  │
│   │  FMS - Process Snippet Files      │ NO CHANGE  │ None                          │  │
│   │  FMS - Process Modular CSV Files  │ NO CHANGE  │ None                          │  │
│   │  MTD - Hourly FMS                 │ MODIFY     │ Update job chain              │  │
│   │  MRD - Elevation - Process Data   │ MODIFY     │ Change output destination     │  │
│   │  MTD Upload - Elevation           │ DISABLE    │ Remove from chain             │  │
│   │  MTD Publish - Elevation          │ DISABLE    │ Remove from chain             │  │
│   │  MTD - FMS Cache Update Hourly    │ NO CHANGE  │ None                          │  │
│   │  MTD - Live Surface Roads Update  │ NO CHANGE  │ None                          │  │
│   │  FMS - Archive Snippet Files      │ NO CHANGE  │ None                          │  │
│   └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
│   NEW JOBS (OPTIONAL):                                                                 │
│                                                                                         │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│   │  • FMS - Output Cleanup           │ Cleanup old output folders                  │  │
│   │  • FMS - Publishing Integration   │ If using separate job for publishing call  │  │
│   └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
│   MULTIJOB CHAIN COMPARISON:                                                           │
│                                                                                         │
│   EXISTING:                                                                            │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│   │  Process Snippet → Process Data → Upload → Publish → Cache Update              │  │
│   └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
│   PROPOSED:                                                                            │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│   │  Process Snippet → Process Data → [Existing Solution] → Cache Update           │  │
│   └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

#### 3. Risk Assessment

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              RISK ASSESSMENT                                            │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                         │
│   HIGH PRIORITY RISKS:                                                                 │
│                                                                                         │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│   │  RISK                         │ LIKELIHOOD │ IMPACT  │ MITIGATION               │  │
│   │  ─────────────────────────────┼────────────┼─────────┼──────────────────────── │  │
│   │  Existing publishing solution │ LOW        │ HIGH    │ Validate solution API   │  │
│   │  incompatibility              │            │         │ before development      │  │
│   │                               │            │         │                          │  │
│   │  Integration timing issues    │ MEDIUM     │ MEDIUM  │ Implement retry logic   │  │
│   │  (hourly processing)          │            │         │ and monitoring          │  │
│   │                               │            │         │                          │  │
│   │  Data loss during handoff     │ LOW        │ HIGH    │ Add validation checks   │  │
│   │                               │            │         │ and confirmation logs   │  │
│   │                               │            │         │                          │  │
│   │  Schedman service disruption  │ LOW        │ HIGH    │ Coordinate migration    │  │
│   │                               │            │         │ window with Schedman    │  │
│   └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
│   MEDIUM PRIORITY RISKS:                                                               │
│                                                                                         │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│   │  • Output folder space management (new cleanup job needed)                      │  │
│   │  • Parallel processing conflicts with existing solution                         │  │
│   │  • Metadata format compatibility                                                │  │
│   │  • Error state handling during transition                                       │  │
│   └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
│   LOW PRIORITY RISKS:                                                                  │
│                                                                                         │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│   │  • Cache update timing (minimal impact expected)                                │  │
│   │  • Archive job compatibility (no change expected)                               │  │
│   │  • Monitoring job adjustments (minor updates)                                   │  │
│   └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

#### 4. Benefits Analysis

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              BENEFITS ANALYSIS                                          │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                         │
│   TECHNICAL BENEFITS:                                                                  │
│                                                                                         │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│   │                                                                                 │  │
│   │   1. REDUCED CODE DUPLICATION                                                  │  │
│   │      • Eliminates duplicate publishing logic                                   │  │
│   │      • Leverages tested, proven existing solution                              │  │
│   │      • Single point of maintenance for publishing                              │  │
│   │                                                                                 │  │
│   │   2. SIMPLIFIED ARCHITECTURE                                                   │  │
│   │      • Fewer Jenkins jobs to manage                                            │  │
│   │      • Clearer separation of concerns                                          │  │
│   │      • Easier troubleshooting                                                  │  │
│   │                                                                                 │  │
│   │   3. IMPROVED MAINTAINABILITY                                                  │  │
│   │      • FMS workflow focuses on data processing                                 │  │
│   │      • Publishing updates apply automatically                                  │  │
│   │      • Reduced testing surface area                                            │  │
│   │                                                                                 │  │
│   │   4. BETTER CONSISTENCY                                                        │  │
│   │      • All raster publishing uses same method                                  │  │
│   │      • Standardized metadata format                                            │  │
│   │      • Consistent error handling                                               │  │
│   │                                                                                 │  │
│   └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
│   OPERATIONAL BENEFITS:                                                                │
│                                                                                         │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│   │                                                                                 │  │
│   │   • Reduced support burden (fewer custom components)                           │  │
│   │   • Easier onboarding for new team members                                     │  │
│   │   • Improved monitoring through centralized publishing                         │  │
│   │   • Better audit trail for data lineage                                        │  │
│   │                                                                                 │  │
│   └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
│   POTENTIAL PERFORMANCE BENEFITS:                                                      │
│                                                                                         │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│   │                                                                                 │  │
│   │   • Possibly faster job completion (fewer steps)                               │  │
│   │   • Reduced SDE connection overhead                                            │  │
│   │   • Better resource utilization                                                │  │
│   │                                                                                 │  │
│   └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

#### 5. Migration Plan

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              MIGRATION PLAN                                             │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                         │
│   PHASE 1: PREPARATION                                                                 │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│   │  □ Validate existing publishing solution API/interface                         │  │
│   │  □ Document input parameters and expected outputs                              │  │
│   │  □ Create output folder structure and permissions                              │  │
│   │  □ Notify Schedman team of planned changes                                     │  │
│   │  □ Create rollback procedure                                                   │  │
│   └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
│   PHASE 2: DEVELOPMENT                                                                 │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│   │  □ Implement output handler module                                             │  │
│   │  □ Implement integration layer                                                 │  │
│   │  □ Modify MTD Process Data job                                                 │  │
│   │  □ Create metadata.json generator                                              │  │
│   │  □ Unit testing                                                                │  │
│   └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
│   PHASE 3: TESTING (DEV ENVIRONMENT)                                                   │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│   │  □ Test single site (WB) end-to-end                                            │  │
│   │  □ Verify raster output quality                                                │  │
│   │  □ Confirm publishing solution integration                                     │  │
│   │  □ Validate cache update functionality                                         │  │
│   │  □ Test error scenarios and recovery                                           │  │
│   │  □ Test parallel processing (all sites)                                        │  │
│   └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
│   PHASE 4: STAGING/UAT                                                                 │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│   │  □ Deploy to staging environment                                               │  │
│   │  □ Run parallel with existing workflow (shadow mode)                           │  │
│   │  □ Compare outputs between existing and new workflow                           │  │
│   │  □ Performance testing under load                                              │  │
│   │  □ Schedman team validation                                                    │  │
│   └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
│   PHASE 5: PRODUCTION DEPLOYMENT                                                       │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│   │  □ Schedule maintenance window with Schedman                                   │  │
│   │  □ Deploy new configuration                                                    │  │
│   │  □ Disable old MTD Upload/Publish jobs                                         │  │
│   │  □ Monitor first processing cycles                                             │  │
│   │  □ Verify service continuity                                                   │  │
│   └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
│   PHASE 6: POST-DEPLOYMENT                                                             │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│   │  □ Monitor for 1 week minimum                                                  │  │
│   │  □ Remove deprecated code (after stabilization)                                │  │
│   │  □ Update documentation                                                        │  │
│   │  □ Close out migration tasks                                                   │  │
│   └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

#### 6. Rollback Strategy

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              ROLLBACK STRATEGY                                          │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                         │
│   ROLLBACK TRIGGERS:                                                                   │
│   • Data not being published to SDE                                                    │
│   • Schedman reporting stale data                                                      │
│   • Integration errors exceeding threshold                                             │
│   • Performance degradation > 50%                                                      │
│                                                                                         │
│   ROLLBACK PROCEDURE:                                                                  │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│   │                                                                                 │  │
│   │   1. Disable new integration in Jenkins                                        │  │
│   │      • Update MTD - Hourly FMS job configuration                               │  │
│   │      • Point back to original job chain                                        │  │
│   │                                                                                 │  │
│   │   2. Re-enable original jobs                                                   │  │
│   │      • MTD Upload - Elevation                                                  │  │
│   │      • MTD Publish - Elevation                                                 │  │
│   │                                                                                 │  │
│   │   3. Trigger manual processing cycle                                           │  │
│   │      • Run MTD - Hourly FMS manually                                           │  │
│   │      • Verify data flow through original pipeline                              │  │
│   │                                                                                 │  │
│   │   4. Notify stakeholders                                                       │  │
│   │      • Schedman team                                                           │  │
│   │      • GIP team                                                                │  │
│   │                                                                                 │  │
│   └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
│   ESTIMATED ROLLBACK TIME: 15-30 minutes                                               │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Appendices

### Appendix A: Snippet File Processing Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| SourceFolder | Source folder containing snippet files | `<path>` |
| zAdjustment | Z value adjustment (ADPH to AHD) | `3.155` |
| DecimalDigits | Decimal precision in output | `2` |
| GridSize | FMS grid cell size (meters) | `2` |
| MaxZ | Maximum Z value filter | `4000.0` |
| FileFilter | Regex filter for snippet files | `ER_2018092010*.snp` |
| InputSpatialReference | Input .prj file path | `<path>` |
| OutputSpatialReference | Output .prj file path | `<path>` |
| OutputCSV | Output CSV filename | `<path>` |
| AOI | Area of Interest feature class | `<path>` |
| AOIWhere | Where clause for AOI | `MineSite='ER'` |
| Despike | Enable smoothing algorithm | `true/false` |
| MinNeighbours | Minimum neighbor points | `2` |

### Appendix B: Environment Configuration

| Environment | FMS Landing Zone Path |
|-------------|----------------------|
| DEV | `<Path where FMS Uploads>` |
| PROD | `<Path where FMS Uploads>` |

### Appendix C: Contact Information

| Role | Team/Person | Notification Required |
|------|------------|----------------------|
| GIP File Delivery | Jerome Green | Alert on file delivery issues |
| Production Scheduling | Schedman Team | Maintenance activities |
| GIS Support | GIS Team | System changes |

### Appendix D: Glossary

| Term | Definition |
|------|------------|
| FMS | Fleet Management System |
| GIP | Global Integration Platform |
| MTD | Mine Technical Data |
| SDE | Spatial Database Engine |
| MGA50 | Map Grid of Australia Zone 50 |
| WB94/ER94 | Site-specific coordinate systems |
| TIN | Triangulated Irregular Network |
| AOI | Area of Interest |
| ADPH | Australian Datum Perth Height |
| AHD | Australian Height Datum |

---

**Document End**

*Last Updated: 2025-12-10*
