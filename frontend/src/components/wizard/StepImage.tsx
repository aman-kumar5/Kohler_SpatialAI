import React, { useRef, useState } from 'react';

interface Props { onNext: () => void; onBack: () => void; isFirst: boolean; isLast: boolean; }

export default function StepImage({ onNext, onBack }: Props) {
  const [images, setImages] = useState<{ url: string; name: string }[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);
  const addImages = (files: FileList | null) => {
    if (!files) return;
    const next = Array.from(files).filter(file => file.type.startsWith('image/')).slice(0, 5 - images.length)
      .map(file => ({ url: URL.createObjectURL(file), name: file.name }));
    setImages(current => [...current, ...next]);
  };
  const remove = (url: string) => setImages(current => {
    URL.revokeObjectURL(url);
    return current.filter(image => image.url !== url);
  });
  return (
    <div className="step-card">
      <p className="eyebrow">STEP 2 OF 6</p>
      <h2>Reference image</h2>
      <p className="step-desc">Upload an inspiration photo (optional). Image analysis will be added in a future release.</p>

      <div className="upload-zone" onDragOver={event => event.preventDefault()} onDrop={event => { event.preventDefault(); addImages(event.dataTransfer.files); }}>
        <span className="upload-icon">🖼</span>
        <p>Drag & drop a photo here, or click to browse</p>
        <input ref={inputRef} type="file" accept="image/*" multiple style={{ display: 'none' }} id="img-upload" onChange={event => addImages(event.target.files)} />
        <label htmlFor="img-upload" className="btn-secondary">Browse images</label>
        <p className="upload-note">Up to five reference images. They are kept locally in this session; visual analysis is a future enhancement.</p>
      </div>
      {images.length > 0 && <div className="reference-image-grid" aria-label="Selected reference images">
        {images.map(image => <figure key={image.url} className="reference-image-thumb"><img src={image.url} alt={`Reference: ${image.name}`} /><button onClick={() => remove(image.url)} aria-label={`Remove ${image.name}`}>×</button><figcaption>{image.name}</figcaption></figure>)}
      </div>}

      <div className="step-actions">
        <button className="btn-ghost" onClick={onBack}>← Back</button>
        <button className="btn-primary" onClick={onNext}>Next: Style →</button>
      </div>
    </div>
  );
}
