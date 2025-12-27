import React, { useState } from 'react';

interface TooltipProps {
    content: string;
    children: React.ReactNode;
    position?: 'top' | 'bottom' | 'left' | 'right';
}

export const Tooltip = ({ content, children, position = 'top' }: TooltipProps) => {
    const [visible, setVisible] = useState(false);

    const getPositionStyle = (): React.CSSProperties => {
        const base: React.CSSProperties = {
            position: 'absolute',
            padding: '6px 12px',
            backgroundColor: 'rgba(30, 30, 30, 0.95)',
            color: 'white',
            fontSize: '12px',
            fontWeight: 500,
            borderRadius: '8px',
            whiteSpace: 'nowrap',
            zIndex: 9999,
            pointerEvents: 'none',
            opacity: visible ? 1 : 0,
            transform: visible ? 'translateY(0) scale(1)' : 'translateY(4px) scale(0.95)',
            transition: 'all 0.15s cubic-bezier(0.4, 0, 0.2, 1)',
            boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
        };

        switch (position) {
            case 'top':
                return { ...base, bottom: '100%', left: '50%', marginBottom: '8px', marginLeft: '-50%' };
            case 'bottom':
                return { ...base, top: '100%', left: '50%', marginTop: '8px', marginLeft: '-50%' };
            case 'left':
                return { ...base, right: '100%', top: '50%', marginRight: '8px', transform: `translateY(-50%) ${visible ? 'scale(1)' : 'scale(0.95)'}` };
            case 'right':
                return { ...base, left: '100%', top: '50%', marginLeft: '8px', transform: `translateY(-50%) ${visible ? 'scale(1)' : 'scale(0.95)'}` };
            default:
                return base;
        }
    };

    return (
        <div
            style={{ position: 'relative', display: 'inline-flex' }}
            onMouseEnter={() => setVisible(true)}
            onMouseLeave={() => setVisible(false)}
        >
            {children}
            <div style={getPositionStyle()}>
                {content}
            </div>
        </div>
    );
};
