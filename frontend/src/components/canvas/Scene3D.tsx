import React, { memo, useEffect } from 'react';
import { Canvas, useThree } from '@react-three/fiber';
import { Box, Grid, OrbitControls, Text } from '@react-three/drei';
import { useDesignStore } from '../../store';
import type { Design, Fixture, Product, Room } from '../../types';

interface Props { design: Design; room: Room; }
type Wall = 'north' | 'south' | 'east' | 'west';
const mm = (value: number) => value / 1000;

/**
 * Canonical scene convention: DesignState x_mm maps to Three.js X, y_mm maps
 * to Three.js Z, and Three.js Y is vertical. Every wall-anchored assembly
 * (shower, WashStation, toilet, etc) treats its own local +Z as "room-
 * facing" and is yawed by the single wallYaw() mapping below — there is no
 * separate/independent rotation convention for the shower.
 */
function orientedDimensions(product: Product, rotation: Fixture['rotation_deg']) {
  const width = product.width_mm ?? 300;
  const depth = product.depth_mm ?? 300;
  return rotation === 90 || rotation === 270 ? { width: depth, depth: width } : { width, depth };
}

export function showerWallAnchor(fixture: Fixture, product: Product, room: Room): Wall {
  const { width, depth } = orientedDimensions(product, fixture.rotation_deg);
  const distances: [Wall, number][] = [
    ['west', fixture.x_mm],
    ['east', room.width_mm - (fixture.x_mm + width)],
    ['south', fixture.y_mm],
    ['north', room.depth_mm - (fixture.y_mm + depth)]
  ];
  return distances.reduce((nearest, next) => next[1] < nearest[1] ? next : nearest)[0];
}

export interface ShowerWallTransform {
  anchor: Wall;
  /** World-space room-facing normal in Three.js X/Z coordinates. */
  normal: readonly [number, number, number];
  /** Mount origin, inset 20mm from the physical wall to prevent z-fighting. */
  position: readonly [number, number, number];
  rotationY: number;
}

/**
 * Single canonical wall→yaw mapping, shared by every fixture kind (shower,
 * vanity/WashStation, toilet, etc). Local +Z is each assembly's room-facing
 * "forward" axis; this is the one and only place that axis is mapped to a
 * world-space yaw per wall, so 2D, 3D, and validation can never disagree
 * about which way a wall-anchored fixture is meant to face.
 */
function wallYaw(anchor: Wall) {
  return { south: 0, north: Math.PI, west: Math.PI / 2, east: -Math.PI / 2 }[anchor];
}

export function getShowerWallTransform(fixture: Fixture, product: Product, room: Room): ShowerWallTransform {
  const wetZone = getShowerWetZone(fixture, product, room);
  const x = mm(wetZone.x_mm), z = mm(wetZone.y_mm);
  const w = mm(wetZone.width_mm), d = mm(wetZone.depth_mm);
  const anchor = wetZone.anchor;
  // Mount origin at wall center of wetZone (inset 20mm off the wall to avoid z-fighting)
  const positions: Record<Wall, readonly [number, number, number]> = {
    south: [x + w / 2, 0, z + 0.02],
    north: [x + w / 2, 0, z + d - 0.02],
    west: [x + 0.02, 0, z + d / 2],
    east: [x + w - 0.02, 0, z + d / 2],
  };
  const normals: Record<Wall, readonly [number, number, number]> = {
    south: [0, 0, 1],
    north: [0, 0, -1],
    west: [1, 0, 0],
    east: [-1, 0, 0],
  };
  return { anchor, normal: normals[anchor], position: positions[anchor], rotationY: wallYaw(anchor) };
}

/** The exact 900 mm wall-aware wet-zone represented by the 2D plan and API. */
export function getShowerWetZone(fixture: Fixture, product: Product, room: Room) {
  const { width, depth } = orientedDimensions(product, fixture.rotation_deg);
  const zoneWidth = Math.max(width, 900);
  const zoneDepth = Math.max(depth, 900);
  const anchor = showerWallAnchor(fixture, product, room);
  let x = Math.max(0, Math.min(fixture.x_mm, room.width_mm - zoneWidth));
  let y = Math.max(0, Math.min(fixture.y_mm, room.depth_mm - zoneDepth));
  if (anchor === 'west') {
    x = 0;
    y = Math.max(0, Math.min(fixture.y_mm - (zoneDepth - depth) / 2, room.depth_mm - zoneDepth));
  } else if (anchor === 'east') {
    x = Math.max(0, room.width_mm - zoneWidth);
    y = Math.max(0, Math.min(fixture.y_mm - (zoneDepth - depth) / 2, room.depth_mm - zoneDepth));
  } else if (anchor === 'south') {
    x = Math.max(0, Math.min(fixture.x_mm - (zoneWidth - width) / 2, room.width_mm - zoneWidth));
    y = 0;
  } else if (anchor === 'north') {
    x = Math.max(0, Math.min(fixture.x_mm - (zoneWidth - width) / 2, room.width_mm - zoneWidth));
    y = Math.max(0, room.depth_mm - zoneDepth);
  }
  return { x_mm: x, y_mm: y, width_mm: zoneWidth, depth_mm: zoneDepth, anchor };
}

function CameraAutoFit({ room, resetTrigger }: { room: Room; resetTrigger?: number }) {
  const { camera, controls } = useThree();

  useEffect(() => {
    const w = mm(room.width_mm);
    const d = mm(room.depth_mm);

    const centerX = w / 2;
    const centerZ = d / 2;

    const roomExtent = Math.max(w, d);
    const dist = Math.max(3.2, roomExtent * 1.35);

    const posX = centerX + dist * 0.85;
    const posY = 2.4 + dist * 0.45;
    const posZ = centerZ + dist * 1.05;

    camera.position.set(posX, posY, posZ);
    camera.lookAt(centerX, 0.6, centerZ);

    if (controls) {
      (controls as any).target.set(centerX, 0.6, centerZ);
      (controls as any).update();
    }
  }, [room.width_mm, room.depth_mm, resetTrigger, camera, controls]);

  return null;
}

function RoomShell({ room }: { room: Room }) {
  const w = mm(room.width_mm), d = mm(room.depth_mm), h = 2.45;
  const doorW = mm(room.door_width_mm ?? 700), doorOffset = mm(room.door_offset_mm ?? 1000);
  const doorH = 2.1;
  const wall = room.door_wall;
  // Door opens outward (away from the bathroom); only this much interior
  // floor space is reserved as a "keep clear" strip. Kept numerically in
  // sync with the backend's spatial/clearance.py door_swing() depth.
  const CLEARANCE_DEPTH_M = 0.2;

  /* Door 3D position and leaf rotation depending on wall */
  const doorCenter: Record<Room['door_wall'], [number, number, number]> = {
    south: [doorOffset + doorW / 2, doorH / 2, 0],
    north: [doorOffset + doorW / 2, doorH / 2, d],
    west:  [0, doorH / 2, doorOffset + doorW / 2],
    east:  [w, doorH / 2, doorOffset + doorW / 2],
  };

  const doorLeafPos: Record<Room['door_wall'], [number, number, number]> = {
    south: [doorOffset, doorH / 2, -0.02],
    north: [doorOffset, doorH / 2, d + 0.02],
    west:  [-0.02, doorH / 2, doorOffset],
    east:  [w + 0.02, doorH / 2, doorOffset],
  };

  const doorLeafRot: Record<Room['door_wall'], [number, number, number]> = {
    south: [0, Math.PI / 3, 0],
    north: [0, -Math.PI / 3, 0],
    west:  [0, -Math.PI / 3, 0],
    east:  [0, Math.PI / 3, 0],
  };

  // Wall-aware interior clearance decal: a CLEARANCE_DEPTH_M-deep strip that
  // starts exactly at the wall and extends INTO the room (never straddling
  // it), matching clearance.py's box(offset, 0, offset+w, depth) per wall.
  const clearanceRect: Record<Room['door_wall'], { cx: number; cz: number; sx: number; sz: number }> = {
    south: { cx: doorOffset + doorW / 2, cz: CLEARANCE_DEPTH_M / 2, sx: doorW * 0.9, sz: CLEARANCE_DEPTH_M },
    north: { cx: doorOffset + doorW / 2, cz: d - CLEARANCE_DEPTH_M / 2, sx: doorW * 0.9, sz: CLEARANCE_DEPTH_M },
    west:  { cx: CLEARANCE_DEPTH_M / 2, cz: doorOffset + doorW / 2, sx: CLEARANCE_DEPTH_M, sz: doorW * 0.9 },
    east:  { cx: w - CLEARANCE_DEPTH_M / 2, cz: doorOffset + doorW / 2, sx: CLEARANCE_DEPTH_M, sz: doorW * 0.9 },
  };
  const clearance = clearanceRect[wall];

  return (
    <group>
      {/* Floor */}
      <mesh receiveShadow position={[w / 2, 0, d / 2]}>
        <boxGeometry args={[w, 0.035, d]} />
        <meshStandardMaterial color="#E9E4DB" roughness={0.85} />
      </mesh>

      {/* Door Clearance Overlay on Floor — interior-only, 200mm deep */}
      <mesh position={[clearance.cx, 0.021, clearance.cz]}>
        <boxGeometry args={[clearance.sx, 0.002, clearance.sz]} />
        <meshStandardMaterial color="#E0A030" transparent opacity={0.35} />
      </mesh>

      {/* Cutaway Shell Walls */}
      <mesh position={[w / 2, h / 2, 0]}>
        <boxGeometry args={[w, h, 0.04]} />
        <meshStandardMaterial color="#F7F6F2" roughness={0.95} transparent opacity={0.4} depthWrite={false} />
      </mesh>
      <mesh position={[0, h / 2, d / 2]}>
        <boxGeometry args={[0.04, h, d]} />
        <meshStandardMaterial color="#F7F6F2" roughness={0.95} transparent opacity={0.4} depthWrite={false} />
      </mesh>

      {/* 3D Door Frame Outer Molding */}
      <group position={doorCenter[wall]}>
        <Box args={[wall === 'south' || wall === 'north' ? doorW + 0.08 : 0.08, doorH + 0.04, wall === 'west' || wall === 'east' ? doorW + 0.08 : 0.08]} castShadow>
          <meshStandardMaterial color="#5C4837" roughness={0.4} />
        </Box>
      </group>

      {/* 3D Open Door Panel / Leaf */}
      <group position={doorLeafPos[wall]} rotation={doorLeafRot[wall]}>
        <mesh position={[doorW / 2, 0, 0]} castShadow>
          <boxGeometry args={[doorW, doorH - 0.02, 0.04]} />
          <meshStandardMaterial color="#A58B6F" roughness={0.35} />
        </mesh>
        {/* Brass Door Handle / Knob */}
        <mesh position={[doorW - 0.08, 0, 0.035]}>
          <cylinderGeometry args={[0.02, 0.02, 0.05, 12]} />
          <meshStandardMaterial color="#B08D57" metalness={0.85} roughness={0.2} />
        </mesh>
      </group>
    </group>
  );
}

function ShowerAssembly({ fixture, product, room }: { fixture: Fixture; product: Product; room: Room }) {
  const wallTransform = getShowerWallTransform(fixture, product, room);
  const wetZone = getShowerWetZone(fixture, product, room);
  const anchor = wetZone.anchor;
  // The tray and enclosure are the canonical wet-zone, not an arbitrary
  // expansion from the product rectangle. This is identical to the 2D/API rule.
  const x = mm(wetZone.x_mm), z = mm(wetZone.y_mm);
  const trayW = mm(wetZone.width_mm), trayD = mm(wetZone.depth_mm);
  const centerX = x + trayW / 2, centerZ = z + trayD / 2;

  /* ── Determine which wall is the perpendicular second wall (nearest corner) ── */
  const rw = mm(room.width_mm), rd = mm(room.depth_mm);
  const secondWall: Wall =
    anchor === 'west' || anchor === 'east'
      ? (centerZ < rd / 2 ? 'south' : 'north')
      : (centerX < rw / 2 ? 'west' : 'east');

  /* Glass panels go on the 2 open sides (NOT anchor, NOT secondWall) */
  const openSides = (['north', 'south', 'east', 'west'] as Wall[]).filter(s => s !== anchor && s !== secondWall);

  /* Glass panel geometry per side */
  const glassPanels = openSides.map(side => {
    switch (side) {
      case 'north': return { pos: [centerX, 1.05, z + trayD] as [number, number, number], size: [trayW, 2.0, 0.012] as [number, number, number] };
      case 'south': return { pos: [centerX, 1.05, z] as [number, number, number], size: [trayW, 2.0, 0.012] as [number, number, number] };
      case 'east':  return { pos: [x + trayW, 1.05, centerZ] as [number, number, number], size: [0.012, 2.0, trayD] as [number, number, number] };
      case 'west':  return { pos: [x, 1.05, centerZ] as [number, number, number], size: [0.012, 2.0, trayD] as [number, number, number] };
    }
  });

  /* Corner clamp position: intersection of the two glass panels */
  const clampX = openSides.includes('east') ? x + trayW : x;
  const clampZ = openSides.includes('north') ? z + trayD : z;

  return (
    <group>
      {/* Shower Tray Base */}
      <mesh receiveShadow position={[centerX, 0.02, centerZ]}>
        <boxGeometry args={[trayW, 0.04, trayD]} />
        <meshStandardMaterial color="#EAE8E3" roughness={0.3} />
      </mesh>
      {/* Drain Grill */}
      <mesh position={[centerX, 0.041, centerZ]}>
        <cylinderGeometry args={[0.06, 0.06, 0.005, 16]} />
        <meshStandardMaterial color="#A5A198" metalness={0.9} roughness={0.2} />
      </mesh>

      {/* Glass Enclosure — L-shape on open sides */}
      {glassPanels.map((g, i) => (
        <mesh key={i} position={g.pos} castShadow>
          <boxGeometry args={g.size} />
          <meshPhysicalMaterial color="#CBE3E7" transparent opacity={0.25} roughness={0.05} metalness={0.15} transmission={0.9} thickness={0.02} />
        </mesh>
      ))}

      {/* Chrome corner clamps where glass panels meet */}
      <mesh position={[clampX, 1.9, clampZ]}>
        <boxGeometry args={[0.03, 0.06, 0.03]} />
        <meshStandardMaterial color="#B08D57" metalness={0.85} roughness={0.2} />
      </mesh>
      <mesh position={[clampX, 0.4, clampZ]}>
        <boxGeometry args={[0.03, 0.06, 0.03]} />
        <meshStandardMaterial color="#B08D57" metalness={0.85} roughness={0.2} />
      </mesh>

      {/* Shower Column & Fixture Assembly — correctly rotated for anchor wall */}
      <group position={wallTransform.position} rotation={[0, wallTransform.rotationY, 0]}>
        {/* Wall Mounting Plate & Thermostatic Valve */}
        <mesh position={[0, 1.0, 0.02]} castShadow>
          <boxGeometry args={[0.14, 0.22, 0.03]} />
          <meshStandardMaterial color="#B08D57" metalness={0.85} roughness={0.2} />
        </mesh>
        {/* Valve Control Knobs */}
        <mesh position={[0, 1.06, 0.04]} rotation={[Math.PI / 2, 0, 0]}>
          <cylinderGeometry args={[0.025, 0.025, 0.03, 16]} />
          <meshStandardMaterial color="#C5C1B8" metalness={0.9} roughness={0.15} />
        </mesh>
        <mesh position={[0, 0.94, 0.04]} rotation={[Math.PI / 2, 0, 0]}>
          <cylinderGeometry args={[0.025, 0.025, 0.03, 16]} />
          <meshStandardMaterial color="#C5C1B8" metalness={0.9} roughness={0.15} />
        </mesh>

        {/* Vertical Slide Bar */}
        <mesh position={[0, 1.4, 0.03]} castShadow>
          <cylinderGeometry args={[0.012, 0.012, 1.3, 12]} />
          <meshStandardMaterial color="#C5C1B8" metalness={0.92} roughness={0.15} />
        </mesh>

        {/* Overhead Arm Projection — projects forward into enclosure */}
        <mesh position={[0, 2.05, 0.16]} rotation={[Math.PI / 2, 0, 0]} castShadow>
          <cylinderGeometry args={[0.012, 0.012, 0.28, 12]} />
          <meshStandardMaterial color="#C5C1B8" metalness={0.92} roughness={0.15} />
        </mesh>

        {/* Rain Showerhead Disc — horizontal disc above tray */}
        <mesh position={[0, 2.02, 0.28]} rotation={[0, 0, 0]} castShadow>
          <cylinderGeometry args={[0.13, 0.12, 0.025, 24]} />
          <meshStandardMaterial color="#B08D57" metalness={0.85} roughness={0.2} />
        </mesh>
      </group>
    </group>
  );
}

function WashStation({ design, room, selectedSku, onSelect }: { design: Design; room: Room; selectedSku: string | null; onSelect: (sku: string) => void }) {
  const members = design.wash_zone?.members ?? [];
  const fixtures = design.fixtures.filter(fixture => members.includes(fixture.sku));
  const products = fixtures.map(fixture => ({ fixture, product: design.products.find(item => item.sku === fixture.sku) })).filter((item): item is { fixture: Fixture; product: Product } => Boolean(item.product));
  const vanity = products.find(item => item.product.category === 'vanity');
  if (!vanity) return null;

  /* Check if basin and faucet products are explicitly selected in design */
  const basinProduct = design.products.find(item => item.category === 'basin');
  const faucetProduct = design.products.find(item => item.category === 'faucet');

  const rawW = mm(vanity.product.width_mm ?? 300);
  const rawD = mm(vanity.product.depth_mm ?? 300);
  const layoutDims = orientedDimensions(vanity.product, vanity.fixture.rotation_deg);
  const w = rawW, d = rawD;
  const sourceH = vanity.product.height_mm ? mm(vanity.product.height_mm) : 0.72;
  const text = `${vanity.product.name} ${vanity.product.installation_type ?? ''}`.toLowerCase();
  const isWallHung = text.includes('wall') || text.includes('hung');
  const cabinetH = Math.max(0.48, Math.min(sourceH, 0.9));
  const baseY = isWallHung ? 0.18 : 0;
  // Position uses the canonical oriented footprint; geometry uses its catalog
  // dimensions once and is yawed once toward the resolved wall.
  const x = mm(vanity.fixture.x_mm) + mm(layoutDims.width) / 2;
  const z = mm(vanity.fixture.y_mm) + mm(layoutDims.depth) / 2;
  const washWall = design.wash_zone?.wall ?? showerWallAnchor(vanity.fixture, vanity.product, room);

  const basinW = basinProduct ? Math.min(w * .72, mm(basinProduct.width_mm ?? 0.42)) : w * .5;
  const basinD = basinProduct ? Math.min(d * .72, mm(basinProduct.depth_mm ?? 0.32)) : d * .48;
  const basinH = basinProduct ? Math.max(.075, Math.min(.18, mm(basinProduct.height_mm ?? 120))) : .11;
  const selected = fixtures.some(fixture => fixture.sku === selectedSku);

  const rotY = ((vanity.fixture.rotation_deg ?? 0) * Math.PI) / 180;

  return (
    <group position={[x, 0, z]} rotation={[0, rotY, 0]} onClick={(event) => { event.stopPropagation(); onSelect(vanity.fixture.sku); }}>
      {/* Cabinet Base */}
      <Box args={[w, cabinetH, d]} position={[0, baseY + cabinetH / 2, 0]} castShadow receiveShadow>
        <meshStandardMaterial color="#5C4837" roughness={.55} emissive={selected ? '#B08D57' : '#000000'} emissiveIntensity={selected ? .15 : 0} />
      </Box>
      {/* Countertop */}
      <Box args={[w * 1.015, .035, d * 1.015]} position={[0, baseY + cabinetH + .018, 0]} castShadow>
        <meshStandardMaterial color="#F6F4EF" roughness={.18} />
      </Box>

      {/* Basin — Rendered ONLY if basin product selected */}
      {basinProduct && (
        <group position={[0, baseY + cabinetH + basinH / 2 + .035, 0]}>
          <Box args={[basinW, basinH, basinD]} castShadow><meshStandardMaterial color="#FCFCF9" roughness={.12} /></Box>
          <mesh position={[0, basinH / 2 + .004, 0]} rotation={[-Math.PI / 2, 0, 0]}><torusGeometry args={[Math.min(basinW, basinD) * .22, .012, 10, 22]} /><meshStandardMaterial color="#B9B6AF" metalness={.65} roughness={.28} /></mesh>
        </group>
      )}

      {/* Faucet — Rendered ONLY if faucet product selected */}
      {faucetProduct && (() => {
        // Local +Z points from the wall-side faucet base toward the basin.
        const faucetZ = -d / 2 + 0.06;
        const topY = baseY + cabinetH + (basinProduct ? basinH : 0.02) + 0.04;
        return (
          <group position={[0, topY, faucetZ]}>
            {/* Faucet Base Ring */}
            <mesh position={[0, 0.01, 0]} rotation={[-Math.PI / 2, 0, 0]}>
              <cylinderGeometry args={[0.03, 0.03, 0.01, 16]} />
              <meshStandardMaterial color="#B08D57" metalness={0.88} roughness={0.18} />
            </mesh>
            {/* Main Faucet Pillar — vertical */}
            <mesh position={[0, 0.12, 0]} castShadow>
              <cylinderGeometry args={[0.02, 0.024, 0.22, 16]} />
              <meshStandardMaterial color="#B08D57" metalness={0.88} roughness={0.18} />
            </mesh>
            {/* Curved Neck — angled forward toward basin */}
            <mesh position={[0, 0.22, 0.04]} rotation={[0.6, 0, 0]} castShadow>
              <cylinderGeometry args={[0.016, 0.018, 0.1, 16]} />
              <meshStandardMaterial color="#B08D57" metalness={0.88} roughness={0.18} />
            </mesh>
            {/* Spout Tip — horizontal arm over basin */}
            <mesh position={[0, 0.24, 0.1]} rotation={[Math.PI / 2, 0, 0]} castShadow>
              <cylinderGeometry args={[0.014, 0.014, 0.08, 16]} />
              <meshStandardMaterial color="#B08D57" metalness={0.88} roughness={0.18} />
            </mesh>
            {/* Spout Nozzle */}
            <mesh position={[0, 0.235, 0.14]}>
              <cylinderGeometry args={[0.01, 0.006, 0.015, 12]} />
              <meshStandardMaterial color="#9A7B4F" metalness={0.9} roughness={0.15} />
            </mesh>
            {/* Handle Lever — angled to the right */}
            <mesh position={[0.035, 0.19, 0]} rotation={[0, 0, Math.PI / 4]} castShadow>
              <cylinderGeometry args={[0.007, 0.007, 0.07, 12]} />
              <meshStandardMaterial color="#B08D57" metalness={0.88} roughness={0.18} />
            </mesh>
          </group>
        );
      })()}

      {/* A decorative mirror is tied to the WashStation wall */}
      <mesh position={[0, baseY + cabinetH + 0.48, -d / 2 + 0.025]} castShadow>
        <boxGeometry args={[Math.min(w * 0.82, 0.9), 0.62, 0.025]} />
        <meshStandardMaterial color="#BFD2D3" metalness={0.35} roughness={0.12} />
      </mesh>
    </group>
  );
}

function StandardFixture({ fixture, product, room, selected, onClick }: { fixture: Fixture; product: Product; room: Room; selected: boolean; onClick: () => void }) {
  const layoutDims = orientedDimensions(product, fixture.rotation_deg);
  const w = mm(layoutDims.width), d = mm(layoutDims.depth);
  const rawW = mm(product.width_mm ?? 300), rawD = mm(product.depth_mm ?? 300);
  const h = mm(product.height_mm ?? 400), category = product.category;
  const rotY = ((fixture.rotation_deg ?? 0) * Math.PI) / 180;

  return (
    <group
      position={[mm(fixture.x_mm) + w / 2, 0, mm(fixture.y_mm) + d / 2]}
      rotation={[0, rotY, 0]}
      onClick={(event) => { event.stopPropagation(); onClick(); }}
    >
      {category === 'toilet' ? (

        <group>
          {/* Toilet bowl — front half (closer to room center) */}
          <Box args={[rawW * 0.75, h * 0.45, rawD * 0.55]} position={[0, h * 0.225, rawD * 0.05]} castShadow receiveShadow>
            <meshStandardMaterial color="#FAFAF8" roughness={0.15} emissive={selected ? '#B08D57' : '#000000'} emissiveIntensity={selected ? 0.2 : 0} />
          </Box>
          {/* Cistern / tank — rear, against wall */}
          <Box args={[rawW * 0.85, h * 0.55, rawD * 0.32]} position={[0, h * 0.55, -rawD * 0.30]} castShadow receiveShadow>
            <meshStandardMaterial color="#FAFAF8" roughness={0.15} emissive={selected ? '#B08D57' : '#000000'} emissiveIntensity={selected ? 0.2 : 0} />
          </Box>
          {/* Cistern lid */}
          <Box args={[rawW * 0.88, h * 0.04, rawD * 0.34]} position={[0, h * 0.84, -rawD * 0.30]} castShadow>
            <meshStandardMaterial color="#F4F4F0" roughness={0.2} />
          </Box>
        </group>
      ) : (
        <Box args={[rawW, h, rawD]} position={[0, h / 2, 0]} castShadow receiveShadow>
          <meshStandardMaterial
            color={category === 'faucet' ? '#B08D57' : '#FAFAF8'}
            roughness={0.2}
            metalness={category === 'faucet' ? 0.85 : 0.05}
            emissive={selected ? '#B08D57' : '#000000'}
            emissiveIntensity={selected ? 0.25 : 0}
          />
        </Box>
      )}
    </group>
  );
}

function Twin({ design, room }: Props) {
  const { selectedFixtureSku, setSelectedFixture } = useDesignStore();
  const [resetKey, setResetKey] = React.useState(0);
  const w = mm(room.width_mm), d = mm(room.depth_mm);
  const washMemberSkus = new Set(design.wash_zone?.members ?? []);

  return (
    <div className="scene3d-wrap">
      <div className="scene3d-canvas-area">
        <Canvas
          shadows
          dpr={[1, 2]}
          style={{ width: '100%', height: '100%' }}
          camera={{ position: [w * 0.8, 2.5, d * 1.4], fov: 50 }}
          onPointerMissed={() => setSelectedFixture(null)}
        >
          <CameraAutoFit room={room} resetTrigger={resetKey} />
          <color attach="background" args={['#F7F6F2']} />
          <ambientLight intensity={0.92} />
          <hemisphereLight args={['#FFFDF8', '#A79D8D', 1.1]} />
          <directionalLight position={[4, 6, 3]} intensity={1.45} castShadow />
          <RoomShell room={room} />
          <Grid args={[w, d]} position={[w / 2, 0.02, d / 2]} cellSize={0.5} sectionSize={1} cellColor="#E3DCCF" sectionColor="#D6B56D" fadeDistance={15} />
          <WashStation design={design} room={room} selectedSku={selectedFixtureSku} onSelect={setSelectedFixture} />
          {design.fixtures.map((f) => {
            const p = design.products.find((product) => product.sku === f.sku);
            if (!p) return null;
            if (washMemberSkus.has(f.sku)) return null;
            return p.category === 'shower' ? (
              <ShowerAssembly key={f.sku} fixture={f} product={p} room={room} />
            ) : (
              <StandardFixture key={f.sku} fixture={f} product={p} room={room} selected={selectedFixtureSku === f.sku} onClick={() => setSelectedFixture(f.sku)} />
            );
          })}
          <OrbitControls target={[w / 2, 0.8, d / 2]} enableDamping dampingFactor={0.08} maxPolarAngle={Math.PI / 2 - 0.05} minDistance={0.8} maxDistance={Math.max(w, d) * 2.4} />
        </Canvas>
        {/* Fit Room button — resets camera to fully frame the entire bathroom */}
        <button
          onClick={() => setResetKey(k => k + 1)}
          title="Fit Room — show the full bathroom"
          style={{
            position: 'absolute',
            top: '10px',
            right: '10px',
            background: 'rgba(255,255,255,0.88)',
            border: '1px solid #C9B99A',
            borderRadius: '6px',
            padding: '5px 10px',
            fontSize: '12px',
            fontWeight: 600,
            color: '#5A4A3A',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '5px',
            backdropFilter: 'blur(4px)',
            boxShadow: '0 1px 4px rgba(0,0,0,0.12)',
            zIndex: 10,
          }}
        >
          ⊡ Fit Room
        </button>
      </div>
    </div>
  );
}
export default memo(Twin);

