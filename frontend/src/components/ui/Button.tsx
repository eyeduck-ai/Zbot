
import React from 'react';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
    variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
    size?: 'sm' | 'md' | 'lg';
    isLoading?: boolean;
}

export const Button = ({
    variant = 'primary',
    size = 'md',
    isLoading,
    className = '',
    children,
    disabled,
    ...props
}: ButtonProps) => {

    // We are using inline styles for dynamic parts or tailwind classes if configured.
    // Since we are moving to CSS modules or global CSS, let's stick to a clean className approach 
    // but for now I will use standard style objects or utility classes if I had tailwind.
    // IMPORTANT: The user project seems to rely on vanilla CSS. I should write CSS-in-JS or matching styles.
    // To keep it simple and consistent with `index.css`, I'll use a style object map here, 
    // OR strictly use the classes if I were adding a CSS file. 
    // Let's use a hybrid approach: minimal inline styles for structure + classes.

    // Actually, let's create a pure CSS based Button component to avoid bloat.
    // I'll attach a localized <style> or rely on the fact that I can't easily add global classes without polluting.
    // Better approach: Use inline styles for the specific Apple look in this file for simplicity, 
    // OR add a `components.css` later? 
    // The plan said "Redesign core components". Let's use the provided `index.css` variables.

    const getStyle = () => {
        let style: React.CSSProperties = {
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontWeight: 500,
            cursor: disabled || isLoading ? 'not-allowed' : 'pointer',
            border: 'none',
            transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
            opacity: disabled ? 0.6 : 1,
            transform: (disabled) ? 'none' : undefined,
        };

        // Variant Styles
        if (variant === 'primary') {
            style.backgroundColor = 'var(--accent-blue)';
            style.color = 'white';
            style.boxShadow = '0 1px 2px rgba(0,0,0,0.1)';
        } else if (variant === 'secondary') {
            style.backgroundColor = 'white';
            style.color = 'var(--text-primary)';
            style.border = '1px solid var(--border-light)';
            style.boxShadow = '0 1px 2px rgba(0,0,0,0.05)';
        } else if (variant === 'ghost') {
            style.backgroundColor = 'transparent';
            style.color = 'var(--accent-blue)';
        } else if (variant === 'danger') {
            style.backgroundColor = 'var(--accent-red)';
            style.color = 'white';
        }

        // Size Styles
        if (size === 'sm') {
            style.padding = '4px 10px';
            style.fontSize = '12px';
            style.borderRadius = '6px';
        } else if (size === 'md') {
            style.padding = '8px 16px';
            style.fontSize = '14px';
            style.borderRadius = '8px';
        } else if (size === 'lg') {
            style.padding = '12px 24px';
            style.fontSize = '16px';
            style.borderRadius = '10px';
        }

        return style;
    };

    return (
        <button
            {...props}
            style={{ ...getStyle(), ...props.style }}
            disabled={disabled || isLoading}
            onMouseEnter={(e) => {
                if (!disabled && variant === 'primary') e.currentTarget.style.backgroundColor = 'var(--accent-blue-hover)';
                if (!disabled && variant === 'secondary') e.currentTarget.style.backgroundColor = 'var(--bg-hover)';
                if (!disabled && variant === 'ghost') e.currentTarget.style.backgroundColor = 'rgba(0,0,0,0.05)';
            }}
            onMouseLeave={(e) => {
                if (!disabled && variant === 'primary') e.currentTarget.style.backgroundColor = 'var(--accent-blue)';
                if (!disabled && variant === 'secondary') e.currentTarget.style.backgroundColor = 'white';
                if (!disabled && variant === 'ghost') e.currentTarget.style.backgroundColor = 'transparent';
            }}
            onMouseDown={(e) => {
                if (!disabled) e.currentTarget.style.transform = 'scale(0.97)';
            }}
            onMouseUp={(e) => {
                if (!disabled) e.currentTarget.style.transform = 'scale(1)';
            }}
            className={className}
        >
            {isLoading && (
                <span style={{ marginRight: '8px', display: 'inline-block', width: '12px', height: '12px', border: '2px solid currentColor', borderRightColor: 'transparent', borderRadius: '50%', animation: 'spin 1s linear infinite' }}></span>
            )}
            {children}
            <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>
        </button>
    );
};
