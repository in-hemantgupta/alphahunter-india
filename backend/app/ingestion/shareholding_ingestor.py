import yfinance as yf
from app.db.database import SessionLocal
from app.models.shareholding import ShareholdingPattern


class ShareholdingIngestor:

    def fetch_shareholding(self, symbol: str) -> bool:
        try:
            ticker = yf.Ticker(f"{symbol}.NS")
            major_holders = ticker.major_holders
            institutional_holders = ticker.institutional_holders

            session = SessionLocal()
            try:
                promoter_pct = 0
                fii_pct = 0
                dii_pct = 0
                pledge_pct = 0

                if major_holders is not None and not major_holders.empty:
                    for _, row in major_holders.iterrows():
                        pct = row.get('pctHeld', 0) or 0
                        holder = str(row.get('Holder', '')).lower()

                        if 'promoter' in holder or 'insider' in holder:
                            promoter_pct = pct
                        elif 'fii' in holder or 'foreign' in holder:
                            fii_pct = pct
                        elif 'dii' in holder or 'mutual' in holder or 'domestic' in holder:
                            dii_pct = pct

                if institutional_holders is not None and not institutional_holders.empty:
                    for _, row in institutional_holders.iterrows():
                        pct = row.get('pctHeld', 0) or 0
                        holder = str(row.get('Holder', '')).lower()

                        if 'fii' in holder or 'foreign' in holder:
                            fii_pct = max(fii_pct, pct)
                        elif 'dii' in holder or 'mutual' in holder:
                            dii_pct = max(dii_pct, pct)

                quarter_str = "2026-Q2"

                existing = session.query(ShareholdingPattern).filter_by(
                    symbol=symbol,
                    quarter=quarter_str
                ).first()

                if existing:
                    existing.promoter = promoter_pct
                    existing.fii = fii_pct
                    existing.dii = dii_pct
                    existing.pledge = pledge_pct
                else:
                    record = ShareholdingPattern(
                        symbol=symbol,
                        quarter=quarter_str,
                        promoter=promoter_pct,
                        fii=fii_pct,
                        dii=dii_pct,
                        pledge=pledge_pct
                    )
                    session.add(record)

                session.commit()
                return True
            except Exception as e:
                session.rollback()
                print(f"Error saving shareholding for {symbol}: {e}")
                return False
            finally:
                session.close()

        except Exception as e:
            print(f"Error fetching shareholding for {symbol}: {e}")
            return False
