import React, { useRef, useCallback, useEffect, useState } from 'react';
import { Stage, Layer, Rect, Text, Group, Line, Circle } from 'react-konva';
import { useMutation } from '@tanstack/react-query';
import { useDesignStore } from '../../store';
import { api } from '../../api';
import type { Design, Room, Validation } from '../../types';

interface Props {
  design: Design;
  room: Room;
  budget: number;
}

const PAD = 40;

// Colors
const COLOR_ROOM_BG = '#F7F6F2';
const COLOR_ROOM_BORDER = '#141414';
const COLOR_FIXTURE_DEFAULT = '#D9C7A6';
const COLOR_FIXTURE_SELECTED = '#B08D57';
const COLOR_FIXTURE_INVALID = '#F5C6C6';
const COLOR_FIXTURE_INVALID_BORDER = '#B43333';
const COLOR_DOOR_ZONE = 'rgba(240, 180, 50, 0.18)';
const COLOR_DOOR_BORDER = '#E0A030';

function useScale(room: Room, canvasWidth: number, canvasHeight: number) {
  const scaleX = (canvasWidth - PAD * 2) / room.width_mm;
  const scaleY = (canvasHeight - PAD * 2) / room.depth_mm;
  const scale = Math.min(scaleX, scaleY);
  const roomPxW = room.width_mm * scale;
  const roomPxH = room.depth_mm * scale;
  const offsetX = (canvasWidth - roomPxW) / 2;
  const offsetY = (canvasHeight - roomPxH) / 2;
  return { scale, roomPxW, roomPxH, offsetX, offsetY };
}

function doorRect(room: Room, scale: number) {
  const w = room.door_width_mm * scale;
  // Door opens outward (away from the bathroom); only a 200mm interior
  // clearance strip is reserved — kept in sync with the backend's
  // spatial/clearance.py door_swing() depth.
  const depth = 200 * scale;
  switch (room.door_wall) {
    case 'south': return { x: room.door_offset_mm * scale, y: 0, w, h: depth };
    case 'north': return { x: room.door_offset_mm * scale, y: room.depth_mm * scale - depth, w, h: depth };
    case 'west':  return { x: 0, y: room.door_offset_mm * scale, w: depth, h: w };
    case 'east':  return { x: room.width_mm * scale - depth, y: room.door_offset_mm * scale, w: depth, h: w };
  }
}

export function showerWallAttachment(x: number, y: number, width: number, depth: number, room: Room) {
  const choices: Array<['north' | 'south' | 'east' | 'west', number]> = [
    ['west', x],
    ['east', room.width_mm - (x + width)],
    ['south', y],
    ['north', room.depth_mm - (y + depth)]
  ];
  return choices.reduce((nearest, candidate) => candidate[1] < nearest[1] ? candidate : nearest)[0];
}

export function showerEnvelopeRect(x: number, y: number, fw: number, fd: number, room: Room) {
  const side = showerWallAttachment(x, y, fw, fd, room);
  const envW = Math.max(fw, 900);
  const envD = Math.max(fd, 900);
  if (side === 'west') return { x: 0, y: Math.max(0, Math.min(y - (envD - fd) / 2, room.depth_mm - envD)), w: envW, h: envD, side };
  if (side === 'east') return { x: Math.max(0, room.width_mm - envW), y: Math.max(0, Math.min(y - (envD - fd) / 2, room.depth_mm - envD)), w: envW, h: envD, side };
  if (side === 'south') return { x: Math.max(0, Math.min(x - (envW - fw) / 2, room.width_mm - envW)), y: 0, w: envW, h: envD, side };
  return { x: Math.max(0, Math.min(x - (envW - fw) / 2, room.width_mm - envW)), y: Math.max(0, room.depth_mm - envD), w: envW, h: envD, side };
}

function FixtureGlyph({ category, width, height }: { category: string; width: number; height: number }) {
  const stroke = '#776038';
  if (category === 'toilet') return <Group listening={false}><Rect x={width * .16} y={height * .08} width={width * .68} height={height * .3} cornerRadius={Math.min(8, width * .12)} fill="#F9F8F5" stroke={stroke} /><Circle x={width / 2} y={height * .63} radius={Math.min(width, height) * .23} fill="#F9F8F5" stroke={stroke} /></Group>;
  if (category === 'vanity') return <Group listening={false}><Rect x={width * .06} y={height * .1} width={width * .88} height={height * .8} fill="#9A805F" stroke={stroke} /><Circle x={width / 2} y={height * .45} radius={Math.min(width, height) * .22} fill="#F9F8F5" stroke={stroke} /></Group>;
  if (category === 'basin') return <Circle listening={false} x={width / 2} y={height / 2} radius={Math.min(width, height) * .36} fill="#F9F8F5" stroke={stroke} />;
  if (category === 'faucet') return <Group listening={false}><Line points={[width * .3, height * .72, width * .3, height * .26, width * .68, height * .26, width * .68, height * .48]} stroke={stroke} strokeWidth={2} lineCap="round" lineJoin="round" /><Circle x={width * .68} y={height * .5} radius={2} fill={stroke} /></Group>;
  if (category === 'shower') return <Group listening={false}><Circle x={width * .5} y={height * .25} radius={Math.min(width, height) * .14} fill="#D9E8E8" stroke="#4F807A" /><Line points={[width * .5, height * .39, width * .5, height * .84]} stroke="#4F807A" strokeWidth={2} /></Group>;
  return null;
}

export default function FloorPlan2D({ design, room, budget }: Props) {
  const { updateFixturePlacement, setSelectedFixture, selectedFixtureSku } = useDesignStore();
  const [validation, setValidation] = useState<Validation>(design.validation);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const stageHostRef = useRef<HTMLDivElement>(null);
  const [stageSize, setStageSize] = useState({ width: 0, height: 0 });
  const [zoomLevel, setZoomLevel] = useState(100);

  useEffect(() => {
    const host = stageHostRef.current;
    if (!host) return;
    const updateSize = () => {
      const { width, height } = host.getBoundingClientRect();
      setStageSize({ width: Math.floor(width), height: Math.floor(height) });
    };
    updateSize();
    const observer = new ResizeObserver(updateSize);
    observer.observe(host);
    return () => observer.disconnect();
  }, []);

  const validateMutation = useMutation({
    mutationFn: ({ fixtures }: { fixtures: typeof design.fixtures }) =>
      api.validate(room, fixtures, budget),
    onSuccess: (result) => setValidation(result),
  });

  const [positions, setPositions] = useState<Record<string, { x: number; y: number }>>(() => {
    const m: Record<string, { x: number; y: number }> = {};
    design.fixtures.forEach(f => { m[f.sku] = { x: f.x_mm, y: f.y_mm }; });
    return m;
  });

  useEffect(() => {
    const m: Record<string, { x: number; y: number }> = {};
    design.fixtures.forEach(f => { m[f.sku] = { x: f.x_mm, y: f.y_mm }; });
    setPositions(m);
    setValidation(design.validation);
  }, [design]);

  const { scale, roomPxW, roomPxH, offsetX, offsetY } = useScale(room, stageSize.width, stageSize.height);

  const handleDragEnd = useCallback(
    (sku: string, konvaX: number, konvaY: number) => {
      let x_mm = Math.round((konvaX - offsetX) / scale);
      let y_mm = Math.round((konvaY - offsetY) / scale);

      const p = design.products.find(item => item.sku === sku);

      if (p && p.category === 'shower') {
        const w = p.width_mm ?? 300;
        const d = p.depth_mm ?? 300;
        const envW = Math.max(w, 900);
        const envD = Math.max(d, 900);

        const distWest = x_mm;
        const distEast = room.width_mm - (x_mm + w);
        const distSouth = y_mm;
        const distNorth = room.depth_mm - (y_mm + d);

        const walls: Array<['north' | 'south' | 'east' | 'west', number]> = [
          ['west', distWest],
          ['east', distEast],
          ['south', distSouth],
          ['north', distNorth]
        ];
        const nearestWall = walls.reduce((min, cur) => cur[1] < min[1] ? cur : min)[0];

        if (nearestWall === 'west') {
          x_mm = 0;
          y_mm = Math.max(0, Math.min(y_mm, room.depth_mm - envD));
        } else if (nearestWall === 'east') {
          x_mm = Math.max(0, room.width_mm - w);
          y_mm = Math.max(0, Math.min(y_mm, room.depth_mm - envD));
        } else if (nearestWall === 'south') {
          y_mm = 0;
          x_mm = Math.max(0, Math.min(x_mm, room.width_mm - envW));
        } else if (nearestWall === 'north') {
          y_mm = Math.max(0, room.depth_mm - d);
          x_mm = Math.max(0, Math.min(x_mm, room.width_mm - envW));
        }
        setPositions(prev => ({ ...prev, [sku]: { x: x_mm, y: y_mm } }));
        updateFixturePlacement(sku, x_mm, y_mm);
      } else {
        const fw = p?.width_mm ?? 300;
        const fd = p?.depth_mm ?? 300;
        x_mm = Math.max(0, Math.min(x_mm, room.width_mm - fw));
        y_mm = Math.max(0, Math.min(y_mm, room.depth_mm - fd));

        setPositions(prev => {
          const nextPos = { ...prev, [sku]: { x: x_mm, y: y_mm } };
          if (p && (p.category === 'vanity' || p.category === 'basin' || p.category === 'faucet')) {
            design.fixtures.forEach(f => {
              const item = design.products.find(prod => prod.sku === f.sku);
              if (item && (item.category === 'vanity' || item.category === 'basin' || item.category === 'faucet')) {
                nextPos[f.sku] = { x: x_mm, y: y_mm };
              }
            });
          }
          return nextPos;
        });
        updateFixturePlacement(sku, x_mm, y_mm);
      }

    },
    [design.fixtures, design.products, offsetX, offsetY, scale, room, updateFixturePlacement],
  );


  const issuesBySku = new Map<string, string[]>();
  validation.issues.forEach(issue => {
    issue.fixture_skus.forEach(sku => {
      if (!issuesBySku.has(sku)) issuesBySku.set(sku, []);
      issuesBySku.get(sku)!.push(issue.code);
    });
  });

  const door = doorRect(room, scale);

  return (
    <div className="floorplan-wrap">
      {/* Floating Feasibility Badge */}
      <div className="canvas-floating-status">
        <div className={`status-badge-floating ${validation.valid ? 'pass' : 'fail'}`}>
          <span>{validation.valid ? '✓ Design Feasible' : '✕ Validation Warning'}</span>
          <span className="caret">⌄</span>
        </div>
      </div>

      {/* Main canvas area: tool rail | drawing stage */}
      <div className="floorplan-main-row">
        {/* Left Vertical Tool Rail */}
        <div className="canvas-tool-rail">
          <button className="rail-btn active" title="Select (Cursor)">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M3 3l7 18 3-7 7-3L3 3z" />
            </svg>
          </button>
          <button className="rail-btn" title="Pan (Hand)">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 11V6a2 2 0 0 0-4 0v5" />
              <path d="M14 10V4a2 2 0 0 0-4 0v6" />
              <path d="M10 10.5V6a2 2 0 0 0-4 0v8" />
              <path d="M18 11a2 2 0 0 1 4 0v3a8 8 0 0 1-8 8h-2c-2.8 0-4.5-.8-6-2.4L2 13.5l1.5-1.5c.8-.8 2-.8 2.8 0L9 15" />
            </svg>
          </button>
          <button className="rail-btn" title="Zoom In" onClick={() => setZoomLevel(z => Math.min(200, z + 10))}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
              <line x1="11" y1="8" x2="11" y2="14" />
              <line x1="8" y1="11" x2="14" y2="11" />
            </svg>
          </button>
          <button className="rail-btn" title="Zoom Out" onClick={() => setZoomLevel(z => Math.max(50, z - 10))}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
              <line x1="8" y1="11" x2="14" y2="11" />
            </svg>
          </button>
          <button className="rail-btn" title="Fit Room" onClick={() => setZoomLevel(100)}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7" />
            </svg>
          </button>
          <div className="rail-divider"></div>
          <button className="rail-btn" title="Undo">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M3 7v6h6" />
              <path d="M21 17a9 9 0 0 0-9-9 9 9 0 0 0-6 2.3L3 13" />
            </svg>
          </button>
          <button className="rail-btn" title="Redo">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 7v6h-6" />
              <path d="M3 17a9 9 0 0 1 9-9 9 9 0 0 1 6 2.3l3 2.7" />
            </svg>
          </button>
        </div>

        {/* Canvas Stage */}
        <div className="floorplan-stage" ref={stageHostRef}>
        {stageSize.width > 0 && stageSize.height > 0 && (
          <Stage width={stageSize.width} height={stageSize.height} onClick={() => setSelectedFixture(null)}>
            <Layer>
              {/* Dark Room outer border / wall stroke */}
              <Rect
                x={offsetX - 8}
                y={offsetY - 8}
                width={roomPxW + 16}
                height={roomPxH + 16}
                fill="#141414"
                cornerRadius={2}
              />

            {/* Room background tile floor */}
            <Rect
              x={offsetX}
              y={offsetY}
              width={roomPxW}
              height={roomPxH}
              fill={COLOR_ROOM_BG}
            />

            {/* Grid lines (every 600mm) */}
            {Array.from({ length: Math.floor(room.width_mm / 600) }, (_, i) => {
              const px = offsetX + (i + 1) * 600 * scale;
              return <Line key={`gx${i}`} points={[px, offsetY, px, offsetY + roomPxH]} stroke="#E4E0D6" strokeWidth={0.5} />;
            })}
            {Array.from({ length: Math.floor(room.depth_mm / 600) }, (_, i) => {
              const py = offsetY + (i + 1) * 600 * scale;
              return <Line key={`gy${i}`} points={[offsetX, py, offsetX + roomPxW, py]} stroke="#E4E0D6" strokeWidth={0.5} />;
            })}

            {/* Architectural Door Opening & Swing Arc */}
            {door && (() => {
              const doorW = room.door_width_mm * scale;
              const offsetPx = room.door_offset_mm * scale;
              const wall = room.door_wall;

              /* Hinge & Leaf endpoints */
              let hingeX = offsetX, hingeY = offsetY;
              let leafEndX = offsetX, leafEndY = offsetY;
              let arcStartAngle = 0, arcEndAngle = 90;

              if (wall === 'south') {
                hingeX = offsetX + offsetPx;
                hingeY = offsetY;
                leafEndX = hingeX;
                leafEndY = offsetY + doorW;
                arcStartAngle = 0;
                arcEndAngle = 90;
              } else if (wall === 'north') {
                hingeX = offsetX + offsetPx;
                hingeY = offsetY + roomPxH;
                leafEndX = hingeX;
                leafEndY = offsetY + roomPxH - doorW;
                arcStartAngle = 270;
                arcEndAngle = 360;
              } else if (wall === 'west') {
                hingeX = offsetX;
                hingeY = offsetY + offsetPx;
                leafEndX = offsetX + doorW;
                leafEndY = hingeY;
                arcStartAngle = 270;
                arcEndAngle = 360;
              } else if (wall === 'east') {
                hingeX = offsetX + roomPxW;
                hingeY = offsetY + offsetPx;
                leafEndX = offsetX + roomPxW - doorW;
                leafEndY = hingeY;
                arcStartAngle = 90;
                arcEndAngle = 180;
              }

              return (
                <Group key="door-swing-group">
                  {/* Door Swing Required Clearance Rectangle */}
                  <Rect
                    x={offsetX + door.x} y={offsetY + door.y}
                    width={door.w} height={door.h}
                    fill={COLOR_DOOR_ZONE} stroke={COLOR_DOOR_BORDER} strokeWidth={1}
                    dash={[4, 3]}
                    cornerRadius={2}
                  />
                  {/* Wall Opening Cutout / Threshold */}
                  <Rect
                    x={wall === 'south' || wall === 'north' ? offsetX + offsetPx : (wall === 'west' ? offsetX - 8 : offsetX + roomPxW - 2)}
                    y={wall === 'west' || wall === 'east' ? offsetY + offsetPx : (wall === 'south' ? offsetY - 8 : offsetY + roomPxH - 2)}
                    width={wall === 'south' || wall === 'north' ? doorW : 10}
                    height={wall === 'west' || wall === 'east' ? doorW : 10}
                    fill="#F7F6F2"
                    listening={false}
                  />

                  {/* Label */}
                  <Text
                    text="Door Swing / Required Clearance"
                    fontSize={9}
                    fill="#E0A030"
                    x={offsetX + door.x + 6}
                    y={offsetY + door.y + 6}
                    listening={false}
                  />
                </Group>
              );
            })()}

            {/* Installation Envelopes */}
            {design.fixtures.map(f => {
              const product = design.products.find(p => p.sku === f.sku);
              if (!product || product.category !== 'shower') return null;

              let fw = product.width_mm ?? 300;
              let fd = product.depth_mm ?? 300;
              if (f.rotation_deg === 90 || f.rotation_deg === 270) { [fw, fd] = [fd, fw]; }

              const pos = positions[f.sku] ?? { x: f.x_mm, y: f.y_mm };
              const env = showerEnvelopeRect(pos.x, pos.y, fw, fd, room);

              const envPxX = offsetX + env.x * scale;
              const envPxY = offsetY + env.y * scale;
              const envPxW = env.w * scale;
              const envPxH = env.h * scale;

              return (
                <Group key={`env-${f.sku}`} x={envPxX} y={envPxY} listening={false}>
                  <Rect
                    width={envPxW} height={envPxH}
                    stroke="#B08D57" strokeWidth={1}
                    dash={[5, 4]}
                    fill="rgba(176, 141, 87, 0.08)"
                  />
                  <Text
                    text="Shower (900 × 900)"
                    fontSize={9}
                    fill="#5B5852"
                    x={6} y={6}
                  />
                </Group>
              );
            })}

            {/* Fixtures */}
            {(() => {
              const hasVanity = design.products.some(p => p.category === 'vanity');
              return design.fixtures.map(f => {
                const product = design.products.find(p => p.sku === f.sku);
                if (!product) return null;

                // When a vanity is present, basin and faucet belong to the vanity area (do not draw separate boxes)
                if (hasVanity && (product.category === 'basin' || product.category === 'faucet')) {
                  return null;
                }

              let fw = product.width_mm ?? 300;
              let fd = product.depth_mm ?? 300;
              if (f.rotation_deg === 90 || f.rotation_deg === 270) { [fw, fd] = [fd, fw]; }

              const pos = positions[f.sku] ?? { x: f.x_mm, y: f.y_mm };
              const issues = issuesBySku.get(f.sku) ?? [];
              const hasIssue = issues.length > 0;
              const isSelected = selectedFixtureSku === f.sku;

              const px = offsetX + pos.x * scale;
              const py = offsetY + pos.y * scale;
              const pw = fw * scale;
              const ph = fd * scale;

              return (
                <Group
                  key={f.sku}
                  x={px} y={py}
                  draggable
                  onClick={(e) => { e.cancelBubble = true; setSelectedFixture(f.sku); }}
                  onDragEnd={(e) => handleDragEnd(f.sku, e.target.x(), e.target.y())}
                >
                  <Rect
                    width={pw} height={ph}
                    fill={hasIssue ? COLOR_FIXTURE_INVALID : isSelected ? COLOR_FIXTURE_SELECTED : COLOR_FIXTURE_DEFAULT}
                    stroke={hasIssue ? COLOR_FIXTURE_INVALID_BORDER : isSelected ? '#141414' : '#B08D57'}
                    strokeWidth={isSelected ? 2 : 1}
                    cornerRadius={3}
                    shadowEnabled={isSelected}
                    shadowBlur={8}
                    shadowOpacity={0.2}
                  />
                  <FixtureGlyph category={product.category} width={pw} height={ph} />
                  <Text
                    text={(() => {
                      if (product.category !== 'vanity') return product.category;
                      const hasBasin = design.products.some(p => p.category === 'basin');
                      const hasFaucet = design.products.some(p => p.category === 'faucet');
                      if (hasBasin && hasFaucet) return 'Vanity + Basin + Faucet';
                      if (hasBasin) return 'Vanity + Basin';
                      if (hasFaucet) return 'Vanity + Faucet';
                      return 'Vanity';
                    })()}
                    fontSize={Math.max(8, Math.min(11, pw / 6))}
                    fill={hasIssue ? '#B43333' : '#141414'}
                    width={pw}
                    height={ph}
                    align="center"
                    verticalAlign="middle"
                    listening={false}
                  />
                </Group>
              );
            });
          })()}

            {/* Dimension Label (Top Width) */}
            <Text
              text={`↔ Width: ${room.width_mm} mm`}
              x={offsetX} y={Math.max(8, offsetY - 26)}
              width={roomPxW} align="center"
              fontSize={12} fill="#141414" fontWeight="600"
            />
            {/* Dimension Label (Left Depth) */}
            <Group x={Math.max(14, offsetX - 18)} y={offsetY + roomPxH / 2} rotation={-90}>
              <Text
                text={`↕ Depth: ${room.depth_mm} mm`}
                x={-roomPxH / 2}
                y={-6}
                width={roomPxH}
                align="center"
                fontSize={12} fill="#141414" fontWeight="600"
              />
            </Group>
          </Layer>
        </Stage>
      )}
      </div>
      </div>{/* end floorplan-main-row */}
    </div>
  );
}
