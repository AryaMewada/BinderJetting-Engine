# 🏗️ Sand 3D Printer System (Binder Jetting Engine)

## 📌 Overview
This project focuses on the development of a custom Binder Jetting-based Sand 3D Printer, including:

- Custom slicing pipeline  
- G-code generation and post-processing  
- Motion + binder control architecture  
- Hardware integration (printhead, extruder, cooling, etc.)

The system is designed to move beyond dependency on external tools (like Netfabb) and build a fully controllable, in-house printing pipeline.

---

## ⚙️ System Architecture

3D Model → Slicer → Layer Images (TIFF) → G-code → Motion Controller → Print Execution  
                                             ↓  
                                     Binder Control  

---

## 🧩 Modules Developed

### 🔹 1. Custom Slicer (Python + PyQt5)
- Loads and previews sliced layers  
- Displays grayscale/bitmap layer images  
- Real-time slider-based layer navigation  
- Optimized rendering (no lag / no white screen issue)  

Key Features:
- Layer-by-layer visualization  
- UI-based control (no animation clutter)  
- Smooth preview rendering  

---

### 🔹 2. G-code Processing System
- Using Netfabb-generated movement G-code as base  
- Planning to merge:
  - Motion G-code  
  - Binder firing instructions (from images)  

Understanding:
- G-code is the primary driver  
- TIFF/images are secondary (used for binder logic)  

---

### 🔹 3. Motion System
- Evaluating controllers (e.g., Duet)  
- Gearbox updated from 1:10 → 1:25 ratio  

Impact:
- Requires recalibration of extrusion/feed logic  

Architecture:
- Motion controller (axes movement)  
- Binder controller (printhead firing)  

---

### 🔹 4. Printhead Integration
- Target: Industrial inkjet printhead (StarFire 1024S)  
- Working on:
  - Communication interface  
  - Droplet firing synchronized with motion  

---

### 🔹 5. Cooling System
- Requirement: Cool components from ~70°C to room temperature  
- Decision: Use water-based liquid cooling (chiller system)  

---

### 🔹 6. Mechanical Design
- Extruder + gearbox redesign:
  - Reduced spacing between barrel and gearbox  
  - Exploring direct coupling vs coupler  

- Hopper system concept:
  - ~2kg capacity  
  - Vacuum refill system  
  - Sensor-based automatic refill  

---

## 🧠 Key Technical Decisions

- G-code centric architecture (motion is primary)  
- Binder firing synchronized with motion  
- Decoupled control system (motion + binder separate)  
- Custom software stack (no dependency on proprietary slicers)  

---

## 🚧 Current Limitations

- Binder firing not integrated yet  
- No finalized G-code + image merging pipeline  
- Controller selection not finalized  
- Save/Load feature not implemented  
- No real-time hardware synchronization  

---
Dates Pushed -

30-3-26 - Add multiple Objects for rasterization v0.02, Next - Intelligent Packing System
30-3-26 v2- Intelligent Packing System
31-3-26 v3- Integrated a Smart reliable packing system with intigrated application Interface that lets your change setting as well as add stl's
31-3-26 v4- Integrated Live Smooth Sliced layer viewer with Load and Save project Features 