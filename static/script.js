// script.js

// ฟังก์ชันแสดง popup message ด้วย SweetAlert2
function showReply(message, type="info") {
    if (message && message.trim() !== "") {
        Swal.fire({
            title: 'ข้อความอัตโนมัติ',
            text: message,
            icon: type,
            confirmButtonText: 'ปิด',
            timer: 5000,
            timerProgressBar: true,
            position: 'center'
        });
    }
}

// ฟังก์ชันอัปเดต dropdown เวลา
function updateTimes(bookedDict, maintenance=false) {
    const court = document.getElementById("courts").value;
    const timeSelect = document.getElementById("times");
    const bookedTimes = bookedDict[court] || [];

    for (let option of timeSelect.options) {
        // ใช้ข้อความเดิมจาก data-label
        let baseText = option.getAttribute("data-label") || option.value;
        option.text = baseText;
        option.disabled = false;

        // ปิด option ถ้าถูกจองแล้ว
        if (bookedTimes.includes(option.value)) {
            option.disabled = true;
            option.text += " (ถูกจองแล้ว)";
        }

        // ปิดทุก option ถ้า maintenance
        if (maintenance) {
            option.disabled = true;
            option.text += " (ปิดปรับปรุง)";
        }
    }
}

// โหลดหน้าเว็บ
window.onload = function() {
    if (typeof bookedDict !== "undefined") {
        const maintenance = typeof maintenanceStatus !== "undefined" ? maintenanceStatus : false;
        updateTimes(bookedDict, maintenance);
    }
}

// อัปเดตเวลาตามสนามที่เลือก
document.getElementById("courts").addEventListener("change", function() {
    if (typeof bookedDict !== "undefined") {
        const maintenance = typeof maintenanceStatus !== "undefined" ? maintenanceStatus : false;
        updateTimes(bookedDict, maintenance);
    }
});

