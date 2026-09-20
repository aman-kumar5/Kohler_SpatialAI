// Framework-free regression check for the shower wall-anchor -> 3D yaw
// mapping fixed in Scene3D.tsx (Bug #1: shower facing outside the room).
//
// There is no JS/TS test runner in this project (no vitest/jest configured),
// so this intentionally duplicates only the pure rotation math from
// Scene3D.tsx (wallYaw + the shower assembly's local +Z "room-facing"
// convention) and checks it algebraically for all four walls. It has no
// dependencies and can be run directly:
//
//   node scripts/verify_shower_orientation.mjs
//
// If this ever fails, first check that Scene3D.tsx's wallYaw() mapping
// still matches the values asserted below (south:0, north:PI, west:PI/2,
// east:-PI/2) before assuming the room geometry changed.

function wallYaw(anchor) {
  return { south: 0, north: Math.PI, west: Math.PI / 2, east: -Math.PI / 2 }[anchor];
}

// Rotates a local vector (x, z) around the Y axis by theta, matching
// Three.js's rotation convention (same math used by <group rotation={[0, theta, 0]}>).
function rotateY([x, , z], theta) {
  const cos = Math.cos(theta), sin = Math.sin(theta);
  return [x * cos + z * sin, 0, -x * sin + z * cos];
}

// For each wall, the shower assembly's local +Z axis (where the arm/head
// mesh offsets live, e.g. position={[0,2.05,0.16]}) must map to the
// world-space direction that points AWAY from that wall and INTO the room.
const expectedRoomFacingWorldDirection = {
  south: [0, 0, 1],   // near z=0 wall -> room interior is +Z
  north: [0, 0, -1],  // near z=depth wall -> room interior is -Z
  west: [1, 0, 0],    // near x=0 wall -> room interior is +X
  east: [-1, 0, 0],   // near x=width wall -> room interior is -X
};

const LOCAL_FORWARD = [0, 0, 1]; // the shower group's local +Z

let failures = 0;
for (const anchor of ['south', 'north', 'west', 'east']) {
  const theta = wallYaw(anchor);
  const [wx, , wz] = rotateY(LOCAL_FORWARD, theta);
  const [ex, , ez] = expectedRoomFacingWorldDirection[anchor];
  const ok = Math.abs(wx - ex) < 1e-9 && Math.abs(wz - ez) < 1e-9;
  console.log(
    `${anchor.padEnd(6)} wallYaw=${theta.toFixed(4)}  local+Z -> world(${wx.toFixed(2)}, ${wz.toFixed(2)})  expected(${ex}, ${ez})  ${ok ? 'PASS' : 'FAIL'}`,
  );
  if (!ok) failures++;
}

if (failures > 0) {
  console.error(`\n${failures} wall(s) FAILED — the shower assembly would face outside the room.`);
  process.exit(1);
} else {
  console.log('\nAll 4 walls PASS — the shower assembly always faces into the room.');
}
