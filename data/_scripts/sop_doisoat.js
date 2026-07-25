const { Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell, WidthType, ShadingType, VerticalAlign } = require("docx");

const FONT = "Times New Roman";
const metaLine = (label, value) => new Paragraph({
  children: [
    new TextRun({ text: `${label}: `, bold: true, font: FONT }),
    new TextRun({ text: value, font: FONT }),
  ],
});
const heading = (text, level) => new Paragraph({ text, heading: level });
const bullet = (text) => new Paragraph({ children: [new TextRun({ text, font: FONT })], bullet: { level: 0 } });
const numbered = (text) => new Paragraph({
  children: [new TextRun({ text, font: FONT })],
  numbering: { reference: "sop5", level: 0 },
});
const P = (text) => new Paragraph({ children: [new TextRun({ text, font: FONT })], spacing: { after: 120 } });

function cell(text, header) {
  return new TableCell({
    shading: header ? { type: ShadingType.CLEAR, color: "auto", fill: "1F4E78" } : undefined,
    verticalAlign: VerticalAlign.CENTER,
    children: [new Paragraph({
      children: [new TextRun({ text, font: FONT, size: 21, bold: !!header, color: header ? "FFFFFF" : "000000" })],
    })],
  });
}

const table = new Table({
  width: { size: 9000, type: WidthType.DXA },
  columnWidths: [2200, 2400, 2200, 2200],
  rows: [
    new TableRow({ tableHeader: true, children: ["Loại chênh lệch", "Mô tả", "Thời hạn xử lý", "Bộ phận chịu trách nhiệm"].map(t => cell(t, true)) }),
    new TableRow({ children: ["Thiếu ở ManhPay", "Đối tác ghi nhận giao dịch, ManhPay không có", "Trong ngày làm việc kế tiếp", "Operations"].map(t => cell(t)) }),
    new TableRow({ children: ["Thiếu ở đối tác", "ManhPay ghi nhận, đối tác không có", "Trong 2 ngày làm việc", "Operations + đối tác"].map(t => cell(t)) }),
    new TableRow({ children: ["Lệch số tiền", "Cùng mã giao dịch nhưng số tiền khác nhau", "Trong 2 ngày làm việc", "Finance"].map(t => cell(t)) }),
    new TableRow({ children: ["Trùng lặp", "Một giao dịch xuất hiện nhiều lần", "Trong ngày phát hiện", "Engineering"].map(t => cell(t)) }),
  ],
});

const doc = new Document({
  numbering: {
    config: [{ reference: "sop5", levels: [{ level: 0, format: "decimal", text: "%1.", alignment: "start" }] }],
  },
  sections: [{
    properties: { page: { size: { width: 11907, height: 16840 } } },
    children: [
      new Paragraph({ text: "SOP - Quy trình đối soát và bù trừ giao dịch (Reconciliation & Settlement)", heading: HeadingLevel.TITLE }),
      metaLine("Mã tài liệu", "SOP-005"),
      metaLine("Loại tài liệu", "SOP"),
      metaLine("Module", "Doi_Soat"),
      metaLine("Phiên bản", "2.0"),
      metaLine("Trạng thái", "Approved"),
      metaLine("Ngày hiệu lực", "2026-03-01"),
      metaLine("Chủ sở hữu", "Finance & Operations Team"),
      new Paragraph({ text: "" }),

      heading("1. Mục đích", HeadingLevel.HEADING_1),
      P("Quy định quy trình đối soát dữ liệu giao dịch hàng ngày giữa hệ thống ManhPay và các đối tác (ngân hàng, Napas, cổng thanh toán thẻ quốc tế, merchant), nhằm phát hiện và xử lý kịp thời các chênh lệch, đảm bảo không thất thoát tiền của khách hàng và của công ty."),

      heading("2. Phạm vi áp dụng", HeadingLevel.HEADING_1),
      bullet("Toàn bộ giao dịch nạp tiền, rút tiền, thanh toán QR và chuyển tiền liên ngân hàng."),
      bullet("Không áp dụng cho giao dịch chuyển tiền P2P nội bộ (không phát sinh dòng tiền ra ngoài hệ thống)."),

      heading("3. Chu kỳ đối soát", HeadingLevel.HEADING_1),
      bullet("Đối soát tự động: chạy hàng ngày lúc 02:00 giờ Việt Nam cho dữ liệu của ngày liền trước."),
      bullet("Đối soát thủ công: thực hiện khi phát hiện sự cố hoặc khi đối soát tự động báo chênh lệch vượt ngưỡng cho phép."),
      bullet("Đối soát định kỳ tháng: chốt số liệu tài chính, phục vụ báo cáo cho Ban lãnh đạo và cơ quan quản lý."),

      heading("4. Quy trình đối soát tự động", HeadingLevel.HEADING_1),
      numbered("Hệ thống tải file đối soát từ đối tác (định dạng CSV/Excel theo chuẩn từng đối tác)."),
      numbered("Chuẩn hóa dữ liệu về cùng định dạng nội bộ (mã giao dịch, số tiền, thời gian, trạng thái)."),
      numbered("So khớp từng giao dịch theo transaction_reference và idempotency_key."),
      numbered("Phân loại kết quả: khớp hoàn toàn, chênh lệch, hoặc chỉ tồn tại một phía."),
      numbered("Sinh báo cáo đối soát, gửi tự động cho đội Operations và Finance trước 08:00."),
      numbered("Các giao dịch chênh lệch được đưa vào hàng đợi xử lý thủ công."),

      heading("5. Phân loại chênh lệch và hướng xử lý", HeadingLevel.HEADING_1),
      table,
      new Paragraph({ text: "" }),

      heading("6. Nguyên tắc xử lý ưu tiên khách hàng", HeadingLevel.HEADING_1),
      P("Trong mọi trường hợp chênh lệch mà khách hàng đã bị trừ tiền nhưng chưa nhận được giá trị tương ứng, ManhPay thực hiện cộng tiền tạm ứng cho khách hàng trong vòng 24 giờ, sau đó tiếp tục làm việc với đối tác để thu hồi. Nguyên tắc này nhằm bảo vệ trải nghiệm và niềm tin của khách hàng, phù hợp cam kết nêu tại FAQ-001 câu 4."),

      heading("7. Chỉ số vận hành (SLA)", HeadingLevel.HEADING_1),
      bullet("Tỷ lệ giao dịch khớp tự động (auto-match rate): mục tiêu trên 99.5%."),
      bullet("Thời gian xử lý xong toàn bộ chênh lệch trong ngày: trước 17:00 ngày làm việc kế tiếp."),
      bullet("Tỷ lệ chênh lệch tồn đọng quá 5 ngày làm việc: bằng 0."),

      heading("8. Lịch sử thay đổi", HeadingLevel.HEADING_1),
      bullet("v1.0 (2025-04-01): Khởi tạo quy trình đối soát thủ công."),
      bullet("v1.5 (2025-10-15): Triển khai đối soát tự động hàng ngày."),
      bullet("v2.0 (2026-03-01): Bổ sung nguyên tắc ưu tiên cộng tiền tạm ứng cho khách hàng sau sự cố INC-001."),
    ],
  }],
});

Packer.toBuffer(doc).then((buf) => require("fs").writeFileSync("SOP_DoiSoat_v2.0.docx", buf));
