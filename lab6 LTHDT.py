"""mã số sinh viên: 202419115
Họ tên: Đoàn Anh Tuấn """


from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Callable, List, Optional, Tuple


# Tiện ích kiểm tra dữ liệu
def currentYear() -> int:
    return datetime.now().year


def vnd(amount) -> str:
    value = Decimal(str(amount)).quantize(Decimal("0.01"))
    text = f"{value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return text[:-3] if text.endswith(",00") else text


def _text(value, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} phải là chuỗi (str)")
    if not value.strip():
        raise ValueError(f"{name} không được rỗng")
    return value.strip()


def _integer(value, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} phải là số nguyên")
    return value


def _positive_integer(value, name: str) -> int:
    value = _integer(value, name)
    if value <= 0:
        raise ValueError(f"{name} phải lớn hơn 0")
    return value


def _money(value, name: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise TypeError(f"{name} phải là số")
    number = Decimal(str(value)) if isinstance(value, float) else Decimal(value)
    if not number.is_finite():
        raise ValueError(f"{name} phải là số hữu hạn")
    if number <= 0:
        raise ValueError(f"{name} phải lớn hơn 0")
    return number


def _datetime(value, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} phải là datetime")
    return value


def _periods(fromPeriod, toPeriod) -> Tuple[int, int]:
    fromPeriod = _positive_integer(fromPeriod, "Tiết bắt đầu")
    toPeriod = _positive_integer(toPeriod, "Tiết kết thúc")
    if fromPeriod > toPeriod:
        raise ValueError("Tiết bắt đầu không được lớn hơn tiết kết thúc")
    return fromPeriod, toPeriod


# Trạng thái và hệ phân cấp ngoại lệ nghiệp vụ
class DeviceStatus(Enum):
    Available = "Available"
    Borrowed = "Borrowed"
    UnderMaintenance = "UnderMaintenance"


class BorrowingException(Exception):
    def __init__(self, message: str, innerException: Optional[Exception] = None):
        super().__init__(message)
        if innerException is not None:
            self.__cause__ = innerException


class DeviceUnavailableException(BorrowingException):
    def __init__(self, deviceId: str, currentStatus: DeviceStatus):
        super().__init__(
            f"Thiết bị '{deviceId}' không sẵn sàng (trạng thái: {currentStatus.name})")
        self.deviceId = deviceId
        self.currentStatus = currentStatus


class BorrowLimitExceededException(BorrowingException):
    def __init__(self, borrowerId: str, maximumDevices: int):
        super().__init__(
            f"Người mượn '{borrowerId}' đã đạt giới hạn {maximumDevices} thiết bị")
        self.borrowerId = borrowerId
        self.maximumDevices = maximumDevices


class InvalidBorrowPeriodException(BorrowingException):
    def __init__(self, deviceId: str, requestedDays: int, maximumDays: int):
        super().__init__(
            f"Số ngày mượn {requestedDays} không hợp lệ cho thiết bị '{deviceId}' "
            f"(phải từ 1 đến {maximumDays} ngày)")
        self.deviceId = deviceId
        self.requestedDays = requestedDays
        self.maximumDays = maximumDays


class DuplicateDeviceException(BorrowingException):
    def __init__(self, deviceId: str):
        super().__init__(f"Thiết bị '{deviceId}' đã có trong phiếu")
        self.deviceId = deviceId


class DeviceNotInSlipException(BorrowingException):
    def __init__(self, deviceId: str, slipId: str):
        super().__init__(f"Thiết bị '{deviceId}' không thuộc phiếu '{slipId}'")
        self.deviceId = deviceId
        self.slipId = slipId


class DeviceAlreadyReturnedException(BorrowingException):
    def __init__(self, deviceId: str):
        super().__init__(f"Thiết bị '{deviceId}' đã được trả trước đó")
        self.deviceId = deviceId


class InvalidReturnDateException(BorrowingException):
    """Bổ sung: ngày trả trước ngày mượn."""

    def __init__(self, deviceId: str, returnedDate: datetime, borrowedDate: datetime):
        super().__init__(
            f"Ngày trả {returnedDate:%d/%m/%Y %H:%M} trước ngày mượn "
            f"{borrowedDate:%d/%m/%Y %H:%M} (thiết bị '{deviceId}')")
        self.deviceId = deviceId
        self.returnedDate = returnedDate
        self.borrowedDate = borrowedDate


# Thiết bị
class TeachingDevice(ABC):
    DEFAULT_MAX_BORROW_DAYS = 1
    OLD_AGE_YEARS = 5
    LATE_FEE_PER_DAY = Decimal("10000")

    def __init__(self, deviceId: str, name: str, yearInUse: int, purchasePrice,
                 maxBorrowDays: Optional[int] = None,
                 status: DeviceStatus = DeviceStatus.Available):
        deviceId = _text(deviceId, "Mã thiết bị")
        name = _text(name, "Tên thiết bị")
        yearInUse = _integer(yearInUse, "Năm đưa vào sử dụng")
        if yearInUse > currentYear():
            raise ValueError("Năm đưa vào sử dụng không được lớn hơn năm hiện tại")
        purchasePrice = _money(purchasePrice, "Giá mua")
        if maxBorrowDays is None:
            maxBorrowDays = self.DEFAULT_MAX_BORROW_DAYS
        maxBorrowDays = _positive_integer(maxBorrowDays, "Số ngày mượn tối đa")
        if not isinstance(status, DeviceStatus):
            raise TypeError("Trạng thái phải là DeviceStatus")
        if status is DeviceStatus.Borrowed:
            raise ValueError("Trạng thái Borrowed chỉ đặt được qua phiếu mượn")

        self._deviceId = deviceId
        self._name = name
        self._yearInUse = yearInUse
        self._purchasePrice = purchasePrice
        self._maxBorrowDays = maxBorrowDays
        self._status = status

    @property
    def deviceId(self) -> str:                 
        return self._deviceId

    @property
    def name(self) -> str:
        return self._name

    @property
    def yearInUse(self) -> int:
        return self._yearInUse

    @property
    def purchasePrice(self) -> Decimal:
        return self._purchasePrice

    @property
    def maxBorrowDays(self) -> int:
        return self._maxBorrowDays

    @property
    def status(self) -> DeviceStatus:
        return self._status

    @property
    def ageInYears(self) -> int:
        return currentYear() - self._yearInUse

    def requiresMaintenance(self) -> bool:
        return (self._status is DeviceStatus.UnderMaintenance
                or self.ageInYears > self.OLD_AGE_YEARS)
        
    def markAsBorrowed(self) -> None:
        if self._status is not DeviceStatus.Available:
            raise DeviceUnavailableException(self._deviceId, self._status)
        self._status = DeviceStatus.Borrowed

    def markAsAvailable(self) -> None:
        self._status = DeviceStatus.Available

    def markUnderMaintenance(self) -> None:
        if self._status is not DeviceStatus.Available:
            raise DeviceUnavailableException(self._deviceId, self._status)
        self._status = DeviceStatus.UnderMaintenance

    @abstractmethod
    def getDeviceType(self) -> str: ...

    @abstractmethod
    def calculateAnnualMaintenanceCost(self) -> Decimal: ...

    def __str__(self) -> str:
        return (f"[{self.getDeviceType()}] {self._deviceId} - {self._name}"
                f" | Năm: {self._yearInUse} | Giá: {vnd(self._purchasePrice)}"
                f" | {self._status.name} | Mượn tối đa: {self._maxBorrowDays} ngày")


class AirConditionerRemote(TeachingDevice):
    DEFAULT_MAX_BORROW_DAYS = 2
    MAINTENANCE_RATE = Decimal("0.05")

    def getDeviceType(self) -> str:
        return "Điều khiển điều hòa"

    def calculateAnnualMaintenanceCost(self) -> Decimal:
        return self._purchasePrice * self.MAINTENANCE_RATE


class Microphone(TeachingDevice):
    DEFAULT_MAX_BORROW_DAYS = 1
    MAINTENANCE_RATE = Decimal("0.08")

    def getDeviceType(self) -> str:
        return "Micro không dây"

    def calculateAnnualMaintenanceCost(self) -> Decimal:
        return self._purchasePrice * self.MAINTENANCE_RATE


class ProjectorRemote(TeachingDevice):
    DEFAULT_MAX_BORROW_DAYS = 3
    MAINTENANCE_RATE = Decimal("0.05")

    def getDeviceType(self) -> str:
        return "Điều khiển máy chiếu"

    def calculateAnnualMaintenanceCost(self) -> Decimal:
        return self._purchasePrice * self.MAINTENANCE_RATE


# Người mượn: interface 
class IBorrower(ABC):
    @property
    @abstractmethod
    def borrowerId(self) -> str: ...

    @property
    @abstractmethod
    def fullName(self) -> str: ...

    @abstractmethod
    def getMaximumDevices(self) -> int: ...


class _BorrowerBase(IBorrower):
    """Phần dữ liệu chung; getMaximumDevices() để từng lớp tự hiện thực."""

    def __init__(self, borrowerId: str, fullName: str):
        self._borrowerId = _text(borrowerId, "Mã người mượn")
        self._fullName = _text(fullName, "Họ tên người mượn")

    @property
    def borrowerId(self) -> str:
        return self._borrowerId

    @property
    def fullName(self) -> str:
        return self._fullName


class Lecturer(_BorrowerBase):
    def getMaximumDevices(self) -> int:
        return 3


class TeachingAssistant(_BorrowerBase):
    def getMaximumDevices(self) -> int:
        return 2


# BorrowItem
class BorrowItem:
    def __init__(self, device: TeachingDevice, borrowedDate: datetime,
                 dueDate: datetime, fromPeriod: int = 1, toPeriod: int = 1):
        if not isinstance(device, TeachingDevice):
            raise TypeError("Device không được null và phải là TeachingDevice")
        _datetime(borrowedDate, "Ngày mượn")
        _datetime(dueDate, "Hạn trả")
        if dueDate < borrowedDate:
            raise ValueError("Hạn trả phải sau hoặc bằng ngày mượn")
        fromPeriod, toPeriod = _periods(fromPeriod, toPeriod)

        self._device = device
        self._borrowedDate = borrowedDate
        self._dueDate = dueDate
        self._fromPeriod = fromPeriod
        self._toPeriod = toPeriod
        self._returnedDate: Optional[datetime] = None

    @property
    def device(self) -> TeachingDevice:
        return self._device

    @property
    def borrowedDate(self) -> datetime:
        return self._borrowedDate

    @property
    def dueDate(self) -> datetime:
        return self._dueDate

    @property
    def fromPeriod(self) -> int:
        return self._fromPeriod

    @fromPeriod.setter
    def fromPeriod(self, value: int) -> None:
        self._fromPeriod, _ = _periods(value, self._toPeriod)

    @property
    def toPeriod(self) -> int:
        return self._toPeriod

    @toPeriod.setter
    def toPeriod(self, value: int) -> None:
        _, self._toPeriod = _periods(self._fromPeriod, value)

    @property
    def returnedDate(self) -> Optional[datetime]:    
        return self._returnedDate

    @property
    def isReturned(self) -> bool:
        return self._returnedDate is not None

    @property
    def lateDays(self) -> int:
        """Số ngày trả muộn (0 nếu chưa trả hoặc trả đúng hạn)."""
        if self._returnedDate is None:
            return 0
        return max(0, (self._returnedDate.date() - self._dueDate.date()).days)

    @property
    def lateFee(self) -> Decimal:
        return self.lateDays * self._device.LATE_FEE_PER_DAY

    def returnItem(self, returnedDate: datetime) -> None:
        """Ghi nhận trả (Return trong đề). Kiểm tra xong mới ghi."""
        if self.isReturned:
            raise DeviceAlreadyReturnedException(self._device.deviceId)
        _datetime(returnedDate, "Ngày trả")
        if returnedDate < self._borrowedDate:
            raise InvalidReturnDateException(
                self._device.deviceId, returnedDate, self._borrowedDate)
        self._returnedDate = returnedDate

    def __str__(self) -> str:
        if not self.isReturned:
            state = "chưa trả"
        elif self.lateDays:
            state = f"trả muộn {self.lateDays} ngày, phí {vnd(self.lateFee)}"
        else:
            state = "trả đúng hạn"
        return (f"{self._device.deviceId} - {self._device.name} | mượn "
                f"{self._borrowedDate:%d/%m/%Y}, hạn {self._dueDate:%d/%m/%Y}, "
                f"tiết {self._fromPeriod}-{self._toPeriod} | {state}")


# BorrowingSlip
class BorrowingSlip:
    def __init__(self, slipId: str, borrower: IBorrower, teachingRoom: str,
                 borrowedDate: Optional[datetime] = None):
        slipId = _text(slipId, "Mã phiếu")
        if not isinstance(borrower, IBorrower):
            raise TypeError("Người mượn không được null và phải là IBorrower")
        teachingRoom = _text(teachingRoom, "Phòng dạy")
        if borrowedDate is None:
            borrowedDate = datetime.now()
        _datetime(borrowedDate, "Ngày mượn")

        self._slipId = slipId
        self._borrower = borrower
        self._teachingRoom = teachingRoom
        self._borrowedDate = borrowedDate
        self._items: List[BorrowItem] = []

    @property
    def slipId(self) -> str:
        return self._slipId

    @property
    def borrower(self) -> IBorrower:
        return self._borrower

    @property
    def teachingRoom(self) -> str:
        return self._teachingRoom

    @property
    def borrowedDate(self) -> datetime:
        return self._borrowedDate

    @property
    def items(self) -> Tuple[BorrowItem, ...]:        # IReadOnlyList
        return tuple(self._items)

    def _findItem(self, deviceId: str) -> Optional[BorrowItem]:
        for item in self._items:
            if item.device.deviceId == deviceId:
                return item
        return None

    def _validateBorrowing(self, device: TeachingDevice, borrowDays: int) -> None:
        if not isinstance(device, TeachingDevice):
            raise TypeError("Thiết bị không được null và phải là TeachingDevice")
        borrowDays = _integer(borrowDays, "Số ngày mượn")
        if borrowDays <= 0 or borrowDays > device.maxBorrowDays:
            raise InvalidBorrowPeriodException(
                device.deviceId, borrowDays, device.maxBorrowDays)
        if self._findItem(device.deviceId) is not None:
            raise DuplicateDeviceException(device.deviceId)
        limit = self._borrower.getMaximumDevices()
        if len(self._items) >= limit:
            raise BorrowLimitExceededException(self._borrower.borrowerId, limit)
        if device.status is not DeviceStatus.Available:
            raise DeviceUnavailableException(device.deviceId, device.status)

    def addDevice(self, device: TeachingDevice, borrowDays: int,
                  fromPeriod: int = 1, toPeriod: int = 1) -> None:
        self._validateBorrowing(device, borrowDays)
        item = BorrowItem(device, self._borrowedDate,
                          self._borrowedDate + timedelta(days=borrowDays),
                          fromPeriod, toPeriod)          # lỗi tiết: chưa đổi gì
        device.markAsBorrowed()
        self._items.append(item)

    def returnDevice(self, deviceId: str, returnedDate: datetime) -> Decimal:
        """Trả thiết bị, trả về phí trả muộn của thiết bị đó."""
        deviceId = _text(deviceId, "Mã thiết bị")
        item = self._findItem(deviceId)
        if item is None:
            raise DeviceNotInSlipException(deviceId, self._slipId)
        item.returnItem(returnedDate)          # đã trả / ngày sai -> ném lỗi
        item.device.markAsAvailable()
        return item.lateFee

    def calculateTotalLateFee(self) -> Decimal:
        return sum((i.lateFee for i in self._items), Decimal(0))

    def getLateItems(self) -> List[BorrowItem]:
        return [i for i in self._items if i.lateDays > 0]

    def getUnreturnedItems(self) -> List[BorrowItem]:
        return [i for i in self._items if not i.isReturned]


# ClassRoom (kết tập với TeachingDevice)
class ClassRoom:
    def __init__(self, roomId: str, roomName: str, capacity: int):
        self._roomId = _text(roomId, "Mã phòng")
        self._roomName = _text(roomName, "Tên phòng")
        self._capacity = _positive_integer(capacity, "Sức chứa")
        self._devices: List[TeachingDevice] = []

    @property
    def roomId(self) -> str:
        return self._roomId

    @property
    def devices(self) -> Tuple[TeachingDevice, ...]:
        return tuple(self._devices)

    def addDevice(self, device: TeachingDevice) -> None:
        if not isinstance(device, TeachingDevice):
            raise TypeError("Thiết bị không được null và phải là TeachingDevice")
        if self.findDevice(device.deviceId) is not None:
            raise ValueError(f"Phòng {self._roomId} đã có thiết bị '{device.deviceId}'")
        self._devices.append(device)

    def removeDevice(self, deviceId: str) -> bool:
        for i, d in enumerate(self._devices):
            if d.deviceId == deviceId:
                del self._devices[i]
                return True
        return False

    def findDevice(self, deviceId: str) -> Optional[TeachingDevice]:
        return next((d for d in self._devices if d.deviceId == deviceId), None)

    def calculateAnnualMaintenanceCost(self) -> Decimal:
        return sum((d.calculateAnnualMaintenanceCost() for d in self._devices),
                   Decimal(0))             # đa hình, không if/switch theo lớp

    def getDevicesRequiringMaintenance(self) -> List[TeachingDevice]:
        return [d for d in self._devices if d.requiresMaintenance()]


# Kiểm thử và chương trình chính 
def show_slip(slip: BorrowingSlip) -> None:
    print(f"  Phiếu {slip.slipId} - {slip.borrower.fullName} - {slip.teachingRoom}")
    for item in slip.items:
        print(f"    + {item}")
    late = slip.getLateItems()
    pending = slip.getUnreturnedItems()
    print("    Trả muộn : " + (", ".join(i.device.deviceId for i in late) or "(không có)"))
    print("    Chưa trả : " + (", ".join(i.device.deviceId for i in pending) or "(không có)"))
    print(f"    Tổng phí trả muộn: {vnd(slip.calculateTotalLateFee())}")


def success_flow() -> None:
    print("\nI. LUỒNG THÀNH CÔNG\n")
    now = currentYear()
    lecturer = Lecturer("GV01", "Nguyễn Văn An")
    remote_pj = ProjectorRemote("DK-MC01", "Điều khiển máy chiếu Epson", now - 2, 500_000)
    remote_ac = AirConditionerRemote("DK-DH01", "Điều khiển điều hòa Daikin", 2019, 300_000)
    mic = Microphone("MIC01", "Micro không dây Shure", now - 1, 2_000_000)
    print("  Đã tạo 1 giảng viên và 3 thiết bị:")
    for d in (remote_pj, remote_ac, mic):
        print(f"    {d}")

    slip = BorrowingSlip("PM001", lecturer, "Phòng A.101", datetime(2026, 10, 12, 7, 0))
    slip.addDevice(remote_pj, 2, 1, 3)       # hạn 14/10
    slip.addDevice(mic, 1, 1, 3)             # hạn 13/10
    print("\n  Sau khi thêm điều khiển máy chiếu và micro:")
    show_slip(slip)

    fee = slip.returnDevice("DK-MC01", datetime(2026, 10, 14, 7, 0))
    print(f"\n  Trả điều khiển máy chiếu đúng hạn, phí: {vnd(fee)}")
    show_slip(slip)

    fee = slip.returnDevice("MIC01", datetime(2026, 10, 15, 7, 0))
    print(f"\n  Trả micro muộn 2 ngày, phí: {vnd(fee)}")
    show_slip(slip)

    print("\n  Phụ: ClassRoom (kết tập) chứa 3 thiết bị trên")
    room = ClassRoom("P101", "Phòng 101", 40)
    for d in (remote_pj, remote_ac, mic):
        room.addDevice(d)
    try:
        room.addDevice(mic)
    except ValueError as ex:
        print(f"    Thêm trùng mã bị từ chối: {ex}")
    print(f"    Chi phí bảo trì dự kiến/năm: {vnd(room.calculateAnnualMaintenanceCost())}")
    print("    Cần bảo trì: " + ", ".join(
        d.deviceId for d in room.getDevicesRequiringMaintenance()))


_results: List[bool] = []


def run_case(title: str, expected: type, action: Callable[[], object],
             isConsistent: Callable[[], bool]) -> None:
    """Main bắt ngoại lệ nghiệp vụ; finally kiểm tra tính nhất quán."""
    print(f"- {title}")
    caught: Optional[BorrowingException] = None
    try:
        action()
    except BorrowingException as ex:
        caught = ex
        print(f"    Bắt được {type(ex).__name__}: {ex}")
    finally:
        consistent = isConsistent()
        ok = isinstance(caught, expected) and consistent
        _results.append(ok)
        print(f"    Đúng loại ngoại lệ: {isinstance(caught, expected)} | "
              f"Trạng thái nhất quán: {consistent} -> {'PASS' if ok else 'FAIL'}")


def exception_flow() -> None:
    print("\nII. LUỒNG PHÁT SINH NGOẠI LỆ\n")
    now = currentYear()
    t0 = datetime(2026, 10, 12, 7, 0)
    lecturer = Lecturer("GV02", "Trần Thị Bình")
    assistant = TeachingAssistant("TG01", "Lê Văn Cường")

    # 1. Điều khiển điều hòa đang UnderMaintenance
    ac_broken = AirConditionerRemote("DK-DH02", "Điều khiển điều hòa hỏng", now - 3,
                                     300_000, status=DeviceStatus.UnderMaintenance)
    slip1 = BorrowingSlip("PM101", lecturer, "Phòng A.102", t0)
    run_case("1. Mượn điều khiển điều hòa đang UnderMaintenance",
             DeviceUnavailableException,
             lambda: slip1.addDevice(ac_broken, 1),
             lambda: ac_broken.status is DeviceStatus.UnderMaintenance
             and len(slip1.items) == 0)

    # 2. Trợ giảng mượn thiết bị thứ ba
    slip2 = BorrowingSlip("PM102", assistant, "Phòng B.201", t0)
    slip2.addDevice(Microphone("MIC10", "Micro 10", now - 1, 1_000_000), 1)
    slip2.addDevice(ProjectorRemote("DK-MC10", "Điều khiển MC 10", now - 1, 400_000), 2)
    third = AirConditionerRemote("DK-DH10", "Điều khiển ĐH 10", now - 1, 300_000)
    run_case("2. Trợ giảng mượn thiết bị thứ ba (giới hạn 2)",
             BorrowLimitExceededException,
             lambda: slip2.addDevice(third, 1),
             lambda: len(slip2.items) == 2 and third.status is DeviceStatus.Available)

    # 3. Thêm cùng một micro hai lần
    mic3 = Microphone("MIC03", "Micro 03", now - 1, 1_000_000)
    slip3 = BorrowingSlip("PM103", lecturer, "Phòng A.103", t0)
    slip3.addDevice(mic3, 1)
    run_case("3. Thêm cùng một micro hai lần", DuplicateDeviceException,
             lambda: slip3.addDevice(mic3, 1),
             lambda: len(slip3.items) == 1 and mic3.status is DeviceStatus.Borrowed)

    # 4. Mượn micro 3 ngày, giới hạn 1 ngày
    mic4 = Microphone("MIC04", "Micro 04", now - 1, 1_000_000)
    slip4 = BorrowingSlip("PM104", lecturer, "Phòng A.104", t0)
    run_case("4. Mượn micro 3 ngày (giới hạn 1 ngày)", InvalidBorrowPeriodException,
             lambda: slip4.addDevice(mic4, 3),
             lambda: len(slip4.items) == 0 and mic4.status is DeviceStatus.Available)

    # 5. Trả điều khiển máy chiếu không thuộc phiếu
    slip5 = BorrowingSlip("PM105", lecturer, "Phòng A.105", t0)
    slip5.addDevice(Microphone("MIC05", "Micro 05", now - 1, 1_000_000), 1)
    run_case("5. Trả điều khiển máy chiếu không thuộc phiếu", DeviceNotInSlipException,
             lambda: slip5.returnDevice("DK-MC99", t0 + timedelta(days=1)),
             lambda: len(slip5.getUnreturnedItems()) == 1)

    # 6. Trả cùng một thiết bị hai lần
    first_return = t0 + timedelta(days=1)
    mic6 = Microphone("MIC06", "Micro 06", now - 1, 1_000_000)
    slip6 = BorrowingSlip("PM106", lecturer, "Phòng A.106", t0)
    slip6.addDevice(mic6, 1)
    slip6.returnDevice("MIC06", first_return)
    run_case("6. Trả cùng một thiết bị hai lần", DeviceAlreadyReturnedException,
             lambda: slip6.returnDevice("MIC06", first_return + timedelta(days=3)),
             lambda: slip6.items[0].returnedDate == first_return
             and mic6.status is DeviceStatus.Available)

    # 7. Ngày trả trước ngày mượn
    mic7 = Microphone("MIC07", "Micro 07", now - 1, 1_000_000)
    slip7 = BorrowingSlip("PM107", lecturer, "Phòng A.107", t0)
    slip7.addDevice(mic7, 1)
    run_case("7. Trả thiết bị với ngày trả trước ngày mượn", InvalidReturnDateException,
             lambda: slip7.returnDevice("MIC07", t0 - timedelta(days=1)),
             lambda: not slip7.items[0].isReturned
             and mic7.status is DeviceStatus.Borrowed)

    print(f"\nKẾT QUẢ: {sum(_results)}/{len(_results)} tình huống ngoại lệ đạt.")


def main() -> None:
    success_flow()
    exception_flow()


if __name__ == "__main__":
    main()
