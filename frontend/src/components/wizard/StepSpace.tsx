import React, { useState } from 'react';
import { useDesignStore } from '../../store';
import type { Room } from '../../types';

const bathroomImg = '/bathroom_topview.jpg';

interface Props { onNext: () => void; onBack: () => void; isFirst: boolean; isLast: boolean; }

const DOOR_WALLS: Array<Room['door_wall']> = ['south', 'north', 'west', 'east'];

export default function StepSpace({ onNext, onBack }: Props) {
  const { wizardData, setWizardData } = useDesignStore();
  const { room } = wizardData;
  const [isDraggingOver, setIsDraggingOver] = useState(false);

  const handleNumChange = (k: keyof Room, valStr: string) => {
    const parsed = valStr === '' ? 0 : parseInt(valStr, 10);
    setWizardData({ room: { ...room, [k]: isNaN(parsed) ? 0 : parsed } });
  };

  const update = (k: keyof Room, v: string) =>
    setWizardData({ room: { ...room, [k]: v } });

  const handleImageFile = (file: File) => {
    if (file && file.type.startsWith('image/')) {
      const url = URL.createObjectURL(file);
      setWizardData({ imageUrl: url });
    }
  };

  return (
    <div className="step-card space-step-card">
      <div className="space-layout-grid" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '32px', alignItems: 'start' }}>
        {/* Left Column: Form Controls */}
        <div className="space-form-col">
          <p className="eyebrow" style={{ color: '#B08D57', fontWeight: 600, fontSize: '0.85rem', marginBottom: '4px' }}>Step 1 of 4</p>
          <h2 style={{ fontFamily: 'Playfair Display, Georgia, serif', fontSize: '2rem', fontWeight: 600, color: '#141414', margin: '4px 0 8px 0' }}>Your bathroom space</h2>
          <p className="step-desc" style={{ color: '#666666', fontSize: '0.95rem', marginBottom: '24px', lineHeight: 1.5 }}>
            Enter the room dimensions in millimetres. All spatial validation uses these exact numbers.
          </p>

          <div className="field-grid" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px 20px', marginBottom: '24px' }}>
            <label style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '0.88rem', fontWeight: 600, color: '#222' }}>
              Room width (mm)
              <input
                type="number"
                min={800}
                max={5000}
                step={50}
                value={room.width_mm === 0 ? '' : room.width_mm}
                onChange={e => handleNumChange('width_mm', e.target.value)}
                style={{ padding: '10px 14px', borderRadius: '4px', border: '1px solid #D1CAC0', fontSize: '0.95rem', outline: 'none' }}
              />
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '0.88rem', fontWeight: 600, color: '#222' }}>
              Room depth (mm)
              <input
                type="number"
                min={800}
                max={5000}
                step={50}
                value={room.depth_mm === 0 ? '' : room.depth_mm}
                onChange={e => handleNumChange('depth_mm', e.target.value)}
                style={{ padding: '10px 14px', borderRadius: '4px', border: '1px solid #D1CAC0', fontSize: '0.95rem', outline: 'none' }}
              />
            </label>

            <label style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '0.88rem', fontWeight: 600, color: '#222' }}>
              Door wall
              <select
                value={room.door_wall}
                onChange={e => update('door_wall', e.target.value)}
                style={{ padding: '10px 14px', borderRadius: '4px', border: '1px solid #D1CAC0', fontSize: '0.95rem', background: '#fff', outline: 'none' }}
              >
                {DOOR_WALLS.map(w => (
                  <option key={w} value={w}>
                    {w.charAt(0).toUpperCase() + w.slice(1)}
                  </option>
                ))}
              </select>
            </label>

            <label style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '0.88rem', fontWeight: 600, color: '#222' }}>
              Door offset (mm)
              <input
                type="number"
                min={0}
                max={5000}
                step={25}
                value={room.door_offset_mm === 0 ? '0' : room.door_offset_mm}
                onChange={e => handleNumChange('door_offset_mm', e.target.value)}
                style={{ padding: '10px 14px', borderRadius: '4px', border: '1px solid #D1CAC0', fontSize: '0.95rem', outline: 'none' }}
              />
            </label>

            <label style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '0.88rem', fontWeight: 600, color: '#222' }}>
              Door width (mm)
              <input
                type="number"
                min={600}
                max={1200}
                step={50}
                value={room.door_width_mm === 0 ? '' : room.door_width_mm}
                onChange={e => handleNumChange('door_width_mm', e.target.value)}
                style={{ padding: '10px 14px', borderRadius: '4px', border: '1px solid #D1CAC0', fontSize: '0.95rem', outline: 'none' }}
              />
            </label>
          </div>

          {/* Reference Image / Inspiration Dropzone */}
          <div className="space-image-upload-container" style={{ marginBottom: '24px' }}>
            <span className="upload-section-title" style={{ display: 'block', fontSize: '0.88rem', fontWeight: 600, color: '#222', marginBottom: '8px' }}>Reference Image / Inspiration (Optional)</span>
            {wizardData.imageUrl ? (
              <div className="reference-image-preview-card" style={{ display: 'flex', alignItems: 'center', gap: '16px', background: '#F7F4EE', padding: '12px', borderRadius: '6px', border: '1px solid #D1CAC0' }}>
                <img src={wizardData.imageUrl} alt="Inspiration preview" style={{ width: '64px', height: '64px', objectFit: 'cover', borderRadius: '4px' }} />
                <div className="preview-card-info" style={{ flex: 1, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.9rem', fontWeight: 500, color: '#222' }}>Inspiration photo attached</span>
                  <button type="button" onClick={() => setWizardData({ imageUrl: null })} className="btn-remove-image" style={{ background: 'none', border: 'none', color: '#B43333', cursor: 'pointer', fontWeight: 600 }}>
                    ✕ Remove
                  </button>
                </div>
              </div>
            ) : (
              <div
                className={`upload-zone-centered ${isDraggingOver ? 'dragging' : ''}`}
                onDragOver={e => { e.preventDefault(); setIsDraggingOver(true); }}
                onDragLeave={() => setIsDraggingOver(false)}
                onDrop={e => {
                  e.preventDefault();
                  setIsDraggingOver(false);
                  const file = e.dataTransfer.files?.[0];
                  if (file) handleImageFile(file);
                }}
                onClick={() => document.getElementById('space-image-input')?.click()}
                style={{ border: '2px dashed #D1CAC0', borderRadius: '6px', padding: '20px', textAlign: 'center', cursor: 'pointer', background: isDraggingOver ? '#F0EAE1' : '#FAFAFA' }}
              >
                <input
                  id="space-image-input"
                  type="file"
                  accept="image/*"
                  style={{ display: 'none' }}
                  onChange={e => {
                    const file = e.target.files?.[0];
                    if (file) handleImageFile(file);
                  }}
                />
                <div className="upload-content-wrap">
                  <p className="upload-primary-text" style={{ margin: '0 0 4px 0', fontSize: '0.9rem', color: '#333' }}>
                    <strong>Drag & drop or browse</strong> an inspiration image
                  </p>
                  <p className="upload-secondary-text" style={{ margin: 0, fontSize: '0.8rem', color: '#888' }}>PNG, JPG or WEBP up to 10MB</p>
                </div>
              </div>
            )}
          </div>

          <div className="space-info-box" style={{ background: '#F7F4EE', padding: '14px 18px', borderRadius: '6px', display: 'flex', gap: '12px', alignItems: 'center', marginBottom: '28px' }}>
            <span className="info-icon" style={{ fontSize: '1.2rem', color: '#B08D57' }}>ⓘ</span>
            <p style={{ margin: 0, fontSize: '0.88rem', color: '#555', lineHeight: 1.4 }}>
              These dimensions are used for all spatial calculations, including fixture placement, clearance and circulation.
            </p>
          </div>

          <div className="step-actions" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <button className="btn-ghost" onClick={onBack} disabled style={{ padding: '10px 24px', borderRadius: '4px', border: '1px solid #D1CAC0', background: 'none', cursor: 'not-allowed', color: '#888' }}>
              ← Back
            </button>
            <button className="btn-primary" onClick={onNext} disabled={room.width_mm <= 0 || room.depth_mm <= 0} style={{ padding: '12px 28px', borderRadius: '4px', background: '#9A7846', color: '#fff', border: 'none', fontWeight: 600, cursor: 'pointer' }}>
              Next: Style →
            </button>
          </div>
        </div>

        {/* Right Column: Architectural Top-View Live Room Preview */}
        <div className="space-preview-col" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
          <div className="preview-header-row" style={{ marginBottom: '16px' }}>
            <h3 style={{ margin: 0, fontSize: '1.15rem', fontWeight: 600, color: '#141414' }}>Live room preview</h3>
            <span className="preview-subtext" style={{ fontSize: '0.85rem', color: '#777' }}>Top view (not to scale)</span>
          </div>

          <div className="space-live-preview-box" style={{ position: 'relative', flex: 1, display: 'flex', flexDirection: 'column' }}>
            {/* Top dimension line */}
            <div style={{ position: 'relative', textAlign: 'center', marginBottom: '8px', borderBottom: '1px solid #B08D57', paddingBottom: '4px' }}>
              <span style={{ fontSize: '0.88rem', fontWeight: 600, color: '#222' }}>{room.width_mm} mm</span>
            </div>

            <div style={{ display: 'flex', flex: 1, alignItems: 'stretch', gap: '12px' }}>
              {/* Left vertical dimension line */}
              <div style={{ borderRight: '1px solid #B08D57', paddingRight: '6px', writingMode: 'vertical-rl', transform: 'rotate(180deg)', textAlign: 'center', fontSize: '0.88rem', fontWeight: 600, color: '#222' }}>
                {room.depth_mm} mm
              </div>

              {/* Main Interactive Room Canvas — Utilizing full column height */}
              <div
                className="preview-room-canvas"
                style={{
                  flex: 1,
                  minHeight: '480px',
                  backgroundColor: 'transparent',
                  border: 'none',
                  borderRadius: '4px',
                  overflow: 'hidden',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  padding: 0,
                }}
              >
                <img
                  src={bathroomImg}
                  alt="Live room preview top view"
                  style={{
                    width: '100%',
                    height: '100%',
                    objectFit: 'cover',
                    borderRadius: '4px',
                    display: 'block',
                  }}
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
