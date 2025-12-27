
interface LogoProps {
    className?: string;
    size?: number;
    showText?: boolean;
}

// Logo 圖片路徑 - 更換 logo 只需替換 /public/logo_whiteborder.svg
// 此常數已導出，所有使用 logo 的地方都應該 import 此常數
export const LOGO_IMAGE_PATH = "/logo_whiteborder.svg";

export const Logo = ({ className = "", size = 32, showText = true }: LogoProps) => {
    return (
        <div className={`inline-flex items-center gap-3 ${className}`}>
            {/* Logo Image */}
            <img
                src={LOGO_IMAGE_PATH}
                alt="Zbot Logo"
                style={{
                    width: size,
                    height: size,
                    objectFit: 'contain',
                }}
            />

            {/* Text */}
            {showText && (
                <div className="flex items-center">
                    <span style={{
                        fontFamily: '"Oxanium", sans-serif',
                        fontSize: '2rem',
                        fontWeight: 600,
                        color: '#1f2937',
                        letterSpacing: '-0.025em',
                        wordSpacing: '0.1em',  // 增加單字間距
                    }}>
                        Zbot <span style={{ fontWeight: 400, color: '#4b5563', fontSize: '0.95em' }}>Workflow</span>
                    </span>
                </div>
            )}
        </div>
    );
};
