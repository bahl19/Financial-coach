"""Parses uploaded bank/credit-card statements (CSV or PDF) into a clean
transactions dataframe with columns: date, description, amount."""
import re
import pandas as pd


class DataIngestionAgent:
    name = "Data Ingestion"

    def parse_csv(self, file) -> pd.DataFrame:
        df = pd.read_csv(file)
        df.columns = [c.strip().lower() for c in df.columns]
        col_map = {}
        for c in df.columns:
            if c in ("date", "transaction date", "posted date"):
                col_map[c] = "date"
            elif c in ("description", "memo", "merchant", "name"):
                col_map[c] = "description"
            elif c in ("amount", "amt", "value"):
                col_map[c] = "amount"
        df = df.rename(columns=col_map)

        missing = {"date", "description", "amount"} - set(df.columns)
        if missing:
            raise ValueError(f"CSV is missing required columns: {sorted(missing)}")

        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
        df = df.dropna(subset=["date", "amount"])
        return df[["date", "description", "amount"]].reset_index(drop=True)

    def parse_pdf(self, file) -> pd.DataFrame:
        import pdfplumber

        rows = []
        line_re = re.compile(
            r"(?P<date>\d{1,2}/\d{1,2}/\d{2,4})\s+(?P<desc>.+?)\s+(?P<amount>-?(?:\$|₹|Rs\.?\s?)?\d[\d,]*\.\d{2})$"
        )
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                for line in text.splitlines():
                    m = line_re.match(line.strip())
                    if m:
                        amt = float(m.group("amount").replace("$", "").replace("₹", "").replace("Rs.", "").replace("Rs", "").replace(",", ""))
                        rows.append({
                            "date": m.group("date"),
                            "description": m.group("desc").strip(),
                            "amount": amt,
                        })

        if not rows:
            raise ValueError("Couldn't find any transaction lines in this PDF. Try a CSV export instead.")

        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        return df.dropna(subset=["date"]).reset_index(drop=True)

    def load(self, uploaded_file) -> pd.DataFrame:
        name = uploaded_file.name.lower()
        if name.endswith(".csv"):
            return self.parse_csv(uploaded_file)
        if name.endswith(".pdf"):
            return self.parse_pdf(uploaded_file)
        raise ValueError("Unsupported file type -- please upload a .csv or .pdf statement.")
