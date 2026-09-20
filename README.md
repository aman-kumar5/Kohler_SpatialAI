KOHLER SpatialAI

AI-Powered Bathroom Digital Twin & Spatial Product Optimization Platform

From "Looks Good" to "Actually Fits."

KOHLER SpatialAI is an AI-assisted bathroom design and planning platform combining natural-language AI, real KOHLER product data, deterministic computational geometry, constraint validation, optimization, and interactive 2D/3D visualization.

AI Proposes → Catalog Verifies → Geometry Validates → Scoring Evaluates → Optimization Decides → User Remains in Control.

1. Problem

A bathroom design can look attractive but still be physically impossible or impractical to install. A practical design must satisfy room dimensions, product dimensions, budget, door clearance, fixture spacing, wall placement, installation constraints, circulation, compatibility, and user preferences.

Generative AI alone is not sufficient for exact physical validation. SpatialAI therefore combines AI for language understanding with deterministic engineering for physical validation.

2. Solution

USER REQUIREMENTS
       ↓
AI REQUIREMENT UNDERSTANDING
       ↓
Pydantic STRUCTURED REQUIREMENTS
       ↓
KOHLER PRODUCT CATALOG
       ↓
PRODUCT RETRIEVAL + COMPATIBILITY
       ↓
SPATIAL GEOMETRY VALIDATION
       ↓
CANDIDATE GENERATION
       ↓
HARD CONSTRAINT FILTERING
       ↓
SCORING + OPTIMIZATION
       ↓
CANONICAL DESIGNSTATE
      / \
     /   \
   2D     3D
    \     /
     \   /
      PDF

The same canonical DesignState drives the 2D plan, 3D visualization, validation, optimization and PDF output.

3. Key Innovation

The central innovation is the separation of probabilistic AI from deterministic engineering.

AI handles

Natural-language requirement understanding

Budget and category extraction

Style interpretation

User preferences

Design explanations

What-if requests

Optimization explanations

AI does NOT handle

SKU invention

Price invention

Product dimensions

Physical coordinates

Geometry

Collision detection

Feasibility decisions

Canonical physical state

Deterministic engineering handles

Product grounding

Compatibility

Geometry

Boundary validation

Clearances

Door collision

Fixture overlap

Wall placement

Wet-area constraints

Scoring

Optimization

4. Core Features

Natural-Language Design

Users can describe requirements such as:

"Design a modern bathroom within a ₹1.5 lakh budget. I need a standard toilet, vanity with basin and faucet, and a shower. Prioritize comfortable circulation and avoid conflicts with the door."

Real KOHLER Product Catalog

The project uses backend/app/data/kohler_products.csv containing 69 products across:

Smart Toilets

Standard Toilets

Faucets

Showers

Basins

Vanities

Catalog fields include:

sku, product_name, category, price_inr,
width_mm, depth_mm, height_mm,
installation_type, rough_in_mm, finish,
collection, features, source_url,
dimension_source, dimension_unit,
spatial_ready, dimension_status

Spatial Validation

The backend validates:

Room boundaries

Fixture overlap

Door clearance

Door collision

Fixture clearance

Wall placement

Shower constraints

WashStation footprint

Circulation

Constraint-Aware Optimization

Candidate layouts are generated, invalid layouts are filtered, feasible layouts are scored, and a recommended configuration is produced.

2D Floor Plan

Interactive floor plan showing room boundary, door, clearance, toilet, WashStation, shower and fixture placement.

3D Digital Twin

The same DesignState is rendered using React Three Fiber, Three.js and Drei.

Product Inspector

Displays product name, SKU, price, dimensions, category, finish, collection and installation information.

AI Optimizer

Compares the current design with a proposed design and lets the user accept or discard the recommendation.

PDF Export

Generates a floor-plan/product summary from the canonical DesignState.

5. System Architecture

┌─────────────────────────────────────────────────────────────┐
│                         USER / UI                           │
│ React + TypeScript + Vite + Tailwind + shadcn/ui           │
│ Zustand + React Hook Form + Zod                            │
│ 2D Konva + 3D React Three Fiber + Three.js                 │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                         FASTAPI                             │
│ REST API + Pydantic validation                              │
└───────────────┬───────────────────┬─────────────────────────┘
                │                   │
                ▼                   ▼
       ┌────────────────┐   ┌─────────────────────────┐
       │    AI LAYER    │   │     PRODUCT LAYER      │
       │ Gemini API     │   │ KOHLER CSV             │
       │ Parsing        │   │ Pandas retrieval       │
       │ Explanation    │   │ Product metadata       │
       └───────┬────────┘   └────────────┬────────────┘
               │                         │
               └────────────┬────────────┘
                            ▼
              ┌─────────────────────────┐
              │ DETERMINISTIC ENGINE    │
              │ Shapely                 │
              │ Geometry                │
              │ Collision               │
              │ Clearance               │
              │ Spatial Rules           │
              │ Compatibility           │
              │ WashStation             │
              └────────────┬────────────┘
                           ▼
              ┌─────────────────────────┐
              │ OPTIMIZATION ENGINE     │
              │ Candidate Generation    │
              │ Hard Filtering          │
              │ Scoring                 │
              │ Layout Optimization     │
              └────────────┬────────────┘
                           ▼
                  ┌─────────────────┐
                  │  DESIGNSTATE    │
                  └───────┬─────────┘
                          │
                ┌─────────┴─────────┐
                ▼                   ▼
           2D FLOOR PLAN       3D DIGITAL TWIN
                │                   │
                └─────────┬─────────┘
                          ▼
                      PDF EXPORT

6. End-to-End Workflow

1. User enters room dimensions and requirements
                    ↓
2. Gemini interprets natural language
                    ↓
3. Pydantic validates structured requirements
                    ↓
4. KOHLER catalog is queried
                    ↓
5. Products are filtered for compatibility
                    ↓
6. Candidate layouts are generated
                    ↓
7. Hard spatial constraints are evaluated
                    ↓
8. Invalid candidates are rejected
                    ↓
9. Feasible candidates are scored
                    ↓
10. Optimizer selects a recommendation
                    ↓
11. Canonical DesignState is produced
                    ↓
12. 2D and 3D views are rendered
                    ↓
13. User can inspect/modify/optimize
                    ↓
14. Final design can be exported

7. AI Architecture

Google Gemini is used for language-centric tasks.

Natural Language
       ↓
Gemini
       ↓
Structured JSON
       ↓
Pydantic RequirementSpec
       ↓
Deterministic Backend

Gemini can understand requirements, budget, categories, style, preferences, explanations and what-if requests.

It is deliberately not the source of physical truth.

8. Product Catalog

Source:

backend/app/data/kohler_products.csv

The catalog contains 69 products.

All physical measurements use millimetres and monetary values use INR.

Product information is grounded in the CSV rather than generated by the LLM.

9. Spatial Intelligence

Spatial validation is performed in the FastAPI backend using deterministic geometry and Shapely.

The bathroom environment is represented using geometric footprints such as:

Room Polygon
Door Polygon
Door Clearance
Toilet Footprint
WashStation Footprint
Shower Envelope
Other Fixtures

The engine evaluates:

Boundary
Overlap
Clearance
Door Collision
Wall Placement
Circulation
Wet Area

A visually plausible design is not considered feasible unless it passes the relevant spatial rules.

10. Hard Constraints vs Soft Objectives

Hard Constraints

These cannot be traded away for a better score:

Fixture remains inside room boundary

Illegal fixture overlap is rejected

Door clearance cannot be violated

WashStation cannot collide with door clearance

Required wall-placement rules must be satisfied

Shower wet-area constraints must be satisfied

Soft Objectives

These influence ranking:

Spatial utilization

Circulation

Budget

Style

Compatibility

Therefore:

Invalid Layout + High Score
          ↓
       REJECTED

11. WashStation Modeling

Vanity, basin and faucet are treated as a coordinated WashStation.

The practical installation footprint can be larger than an individual vanity SKU footprint.

The derived WashStation footprint is used by:

Spatial Validation
       ↓
Optimization
       ↓
2D Visualization
       ↓
3D Visualization
       ↓
PDF Export

This keeps the physical model and visual representation consistent.

12. Door Clearance

The current door model uses:

Door: outward opening
Interior clearance: 200 mm

Door clearance is a hard spatial constraint.

The same geometry is reflected in:

Backend validation

2D floor plan

3D visualization

PDF export

WashStation placement is additionally checked against the door-clearance region.

13. Shower Modeling

The shower is wall-mounted and uses a:

900 × 900 mm

wet-area envelope.

The shower can be centered along a wall rather than being restricted to a corner.

Wall orientation uses a shared wall-to-rotation mapping so that the 2D and 3D representations remain consistent.

14. Product Compatibility

Product selection follows:

User Requirement
       ↓
Category Filtering
       ↓
Catalog Retrieval
       ↓
Compatibility
       ↓
Spatial Validation
       ↓
Scoring

The LLM cannot fabricate a product that is not represented by the catalog.

15. Optimization Engine

Candidate configurations are generated across:

Toilet Wall
Vanity Wall
Shower Wall

and the four walls:

North
South
East
West

This produces:

4 × 4 × 4 = 64

distinct wall-pattern combinations.

The optimization pipeline is:

Candidate Layouts
       ↓
Hard Constraint Filtering
       ↓
Feasible Layouts
       ↓
Multi-objective Scoring
       ↓
Recommended Layout

16. Scoring System

Smart Budget

Metric

Weight

Budget

40%

Spatial

30%

Style

15%

Compatibility

15%

Balanced

Metric

Weight

Spatial

30%

Budget

25%

Style

25%

Compatibility

20%

Premium

Metric

Weight

Style

30%

Spatial

30%

Compatibility

25%

Budget

15%

Final score:

Total Score =
Σ(active weight × metric score)
------------------------------
Σ(active weights)

17. Spatial Fit Score

Spatial Fit =
    0.25 × Boundary
  + 0.15 × Clearance
  + 0.25 × Utilization
  + 0.10 × Circulation
  + 0.10 × Door
  + 0.10 × Wall
  + 0.05 × Wet Zone

This allows the optimizer to distinguish between layouts that are merely valid and layouts that use the space more effectively.

18. Canonical DesignState

The DesignState is the central representation of the bathroom.

Conceptually:

DesignState
│
├── Room
│   ├── Width
│   ├── Length
│   └── Door
│
├── Products
│   ├── Toilet
│   ├── WashStation
│   └── Shower
│
├── Placement
│   ├── Position
│   ├── Wall
│   └── Orientation
│
├── Constraints
└── Scores

The same state drives:

            DesignState
            /    |               /     |              2D      3D     PDF

This avoids separate systems generating inconsistent layouts.

19. 2D Floor Plan

The 2D interface displays:

Room boundary

Dimensions

Door

Door clearance

Toilet

WashStation

Shower

Fixture positions

Wall relationships

The plan is based on actual spatial coordinates rather than arbitrary visual placement.

20. 3D Digital Twin

The 3D visualization uses:

React
  ↓
React Three Fiber
  ↓
Three.js
  ↓
Drei

Coordinate mapping:

Engineering X → Three.js X
Engineering Y → Three.js Z
Height        → Three.js Y

The 3D view represents the same DesignState used by the 2D system.

21. AI Optimizer + Human Approval

Current Design
      ↓
Optimizer
      ↓
Draft Design
      ↓
User Review
    /   \
Accept  Discard

The system does not silently overwrite the user's design.

The user remains in control.

22. PDF Export

PDF output is generated from the canonical DesignState.

The export can contain:

Floor plan

Fixture positions

Product information

Product summary

Design information

The PDF uses the same design coordinates as the application floor plan.

23. Technology Stack

Frontend

Technology

Purpose

React

UI framework

TypeScript

Type safety

Vite

Development/build

Tailwind CSS

Styling

shadcn/ui

UI components

Zustand

Global design state

React Hook Form

Form handling

Zod

Client validation

TanStack Query

API/server state

React Konva / Konva

2D floor plan

React Three Fiber

3D React rendering

Three.js

3D graphics

Drei

R3F helpers

Recharts

Data visualization

Framer Motion

Animation

Lucide React

Icons

React Router

Routing

Backend

Technology

Purpose

Python

Backend language

FastAPI

REST API

Pydantic v2

Validation

SQLAlchemy

Data abstraction

SQLite

Local/demo persistence

Pandas

Catalog processing

NumPy

Numerical operations

Shapely

Computational geometry

ReportLab

PDF generation

AI

Technology

Purpose

Google Gemini API

Requirement understanding

Structured Output

Structured responses

Pydantic

AI output validation

Prompt Engineering

Controlled AI behavior

Provider Failover

API resilience

Testing / Quality

Technology

Purpose

Pytest

Backend testing

Vitest

Frontend unit tests

Playwright

E2E testing

Ruff

Python linting

ESLint

Frontend linting

Prettier

Formatting

24. Project Structure

KOHLER SpatialAI/
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── models.py
│   │   ├── repository.py
│   │   ├── pdf_export.py
│   │   ├── data/
│   │   │   └── kohler_products.csv
│   │   ├── optimizer/
│   │   │   ├── service.py
│   │   │   └── scoring.py
│   │   └── spatial/
│   │       ├── geometry.py
│   │       ├── validation.py
│   │       ├── clearance.py
│   │       ├── collision.py
│   │       ├── rules.py
│   │       ├── compatibility.py
│   │       └── wash_zone.py
│   ├── tests/
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/
│   ├── src/
│   │   ├── store.ts
│   │   ├── api.ts
│   │   ├── types.ts
│   │   └── components/
│   │       ├── AICopilot.tsx
│   │       ├── FloorPlan2D.tsx
│   │       ├── Scene3D.tsx
│   │       ├── Wizard.tsx
│   │       └── ProductInspector.tsx
│   ├── scripts/
│   │   └── verify_shower_orientation.mjs
│   └── package.json
│
├── docs/
│   └── KOHLER_SpatialAI_Prompts_Documentation.pdf
│
└── README.md

25. Backend Architecture

FastAPI
  │
  ├── AI / Requirement Parser
  ├── Product Repository
  ├── Spatial Validation
  ├── Compatibility
  ├── Optimizer
  └── PDF Export

Main responsibilities

main.py

API entry point and routes

models.py

Pydantic/data models

repository.py

Product catalog access

spatial/

Geometry and validation

optimizer/

Candidate generation and scoring

pdf_export.py

PDF generation

26. Frontend Architecture

App
│
├── Landing Page
├── Wizard
│   └── Requirement Input
├── Dashboard
│   ├── AI Copilot
│   ├── Product Inspector
│   ├── 2D Floor Plan
│   ├── 3D Scene
│   └── Optimizer
└── Export

Zustand maintains shared design state while the backend remains the authority for physical validation.

27. API/Data Flow

React Frontend
      │
      │ HTTP
      ▼
FastAPI
      │
      ├──► Gemini
      ├──► KOHLER Catalog
      ├──► Spatial Engine
      └──► Optimizer
                │
                ▼
           DesignState
                │
                ▼
           API Response
                │
                ▼
          React Frontend

28. Environment Configuration

Copy:

backend/.env.example

Configure Gemini keys:

GEMINI_API_KEYS=your_key_1,your_key_2,your_key_3

Keys are tried in order when provider failover is enabled.

Never commit real API keys.

29. Installation

Requirements

Python 3.11+
Node.js 20+
npm
Git

Backend

cd backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000

Backend:

http://localhost:8000

API documentation:

http://localhost:8000/docs

Frontend

Open another terminal:

cd frontend
npm install
npm run dev

Open the local Vite URL shown in the terminal.

30. Testing

Backend:

cd backend
python -m pytest -q

Frontend production build:

cd frontend
npm run build

TypeScript:

cd frontend
npx tsc --noEmit

Shower orientation regression check:

node frontend/scripts/verify_shower_orientation.mjs

The test suite covers areas including:

Fixture overlap

Door collision

Door clearance

WashStation collision

Room boundaries

Budget constraints

Fixture rotation

Multiple room sizes

Missing scoring metrics

DesignState behavior

Spatial scoring

Product compatibility

Shower orientation

31. Reliability and Failure Handling

Gemini failover

Gemini Key 1
     ↓ failure
Gemini Key 2
     ↓ failure
Gemini Key 3
     ↓ failure
Deterministic extraction where supported

The system does not fabricate a provider response.

Structured output

Gemini
  ↓
JSON
  ↓
Pydantic
  ↓
RequirementSpec
  ↓
Backend

AI output must pass validation before entering the application workflow.

32. Security and AI Safety

API keys remain server-side.

Secrets are loaded through environment variables.

Real keys must never be committed.

AI output is schema validated.

Product facts come from the catalog.

Geometry is deterministic.

Hard constraints cannot be overridden by LLM text.

The LLM cannot directly modify physical coordinates.

Optimizer changes require user approval.

33. Why Not Use an LLM for Geometry?

Geometry requires exact numerical reasoning.

Example:

Room = 3000 × 2400 mm
Fixture = 650 × 700 mm
Door clearance = 200 mm

The LLM can understand what these numbers mean, but it should not be the final authority on whether two physical polygons intersect.

Therefore:

LLM
→ semantic understanding

Shapely + deterministic rules
→ physical validation

This improves reliability, reproducibility and testability.

34. Design Philosophy

AI Proposes
     ↓
Catalog Verifies
     ↓
Geometry Validates
     ↓
Scoring Evaluates
     ↓
Optimization Decides
     ↓
User Remains in Control

The project is a decision-support system rather than an autonomous replacement for the user or designer.

35. Sustainability and Business Impact

Potential benefits include:

Reduced uncertainty before purchase

Better product discovery

Reduced redesign iterations

Reduced fit-related installation rework

More efficient bathroom planning

Future water-efficiency-aware product comparison

The current prototype does not claim measured water savings. Water-conservation capabilities can be expanded through validated product-level sustainability metadata.

36. Production Upgrade Path

Database

SQLite → PostgreSQL

Retrieval

Pandas metadata retrieval
        ↓
PostgreSQL + pgvector / dedicated retrieval

Optimization

Custom candidate search
        ↓
OR-Tools / advanced constraint solver

Deployment

Local Prototype
      ↓
Cloud Backend
      ↓
PostgreSQL
      ↓
Object Storage
      ↓
Monitoring

Potential production features:

Authentication

Persistent design history

Real-time inventory

Live pricing

Product availability

Accessibility constraints

Plumbing/electrical constraints

Sustainability metadata

Collaborative design

Mobile support

37. Demo Workflow

Landing Page
     ↓
Create Design
     ↓
Room Dimensions
     ↓
Natural-Language Requirements
     ↓
AI Understanding
     ↓
Generate Design
     ↓
Product Inspection
     ↓
2D Floor Plan
     ↓
3D Bathroom
     ↓
AI Optimizer
     ↓
Accept / Discard
     ↓
PDF Export

Recommended demo input:

"Design a modern 3000 × 2400 mm bathroom within a ₹1.5 lakh budget. I need a standard toilet, vanity with basin and faucet, and a shower. Prioritize comfortable circulation and avoid conflicts with the door."

38. Project Documentation

Prompt documentation:

docs/KOHLER_SpatialAI_Prompts_Documentation.pdf

It covers:

AI system instructions

Requirement parsing

Catalog grounding

Structured output

Prompt engineering

AI optimizer

Explainability

What-if interactions

Safety boundaries

Failure handling

Prompt inventory

Complete AI workflow

39. Future Scope

AI

Multi-turn design refinement

Conversational design editing

Advanced preference understanding

Better explanations

Natural-language spatial edits

Spatial

Accessibility-aware planning

Plumbing constraints

Electrical constraints

Window placement

Structural constraints

Advanced installation envelopes

Products

Real-time inventory

Live pricing

Product substitution

Water-efficiency comparison

Sustainability metadata

Optimization

Multi-objective Pareto optimization

Advanced constraint solvers

Larger product search spaces

Installation-cost optimization

Platform

Accounts

Saved projects

Design history

Designer collaboration

Customer sharing

Cloud deployment

40. Conclusion

KOHLER SpatialAI combines:

Generative AI
      +
Real Product Data
      +
Computational Geometry
      +
Constraint Validation
      +
Optimization
      +
2D Visualization
      +
3D Visualization
      +
PDF Documentation

to create a practical AI-assisted bathroom planning workflow.

The core principle is:

AI proposes. Engineering verifies. The customer decides.

KOHLER SpatialAI

From Looks Good to Actually Fits.