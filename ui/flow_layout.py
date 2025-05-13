from PyQt5.QtWidgets import QLayout
from PyQt5.QtCore import Qt, QSize, QRect, QPoint, QPropertyAnimation


class FlowLayout(QLayout):
    def __init__(self, parent=None, margin=0, spacing=5):
        super().__init__(parent)
        self.setContentsMargins(margin, margin, margin, margin)
        self._spacing = spacing
        self.itemList = []

    def addItem(self, item):
        self.itemList.append(item)

    def count(self):
        return len(self.itemList)

    def itemAt(self, index):
        return self.itemList[index] if 0 <= index < len(self.itemList) else None

    def takeAt(self, index):
        return self.itemList.pop(index) if 0 <= index < len(self.itemList) else None

    def expandingDirections(self):
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self.doLayout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self.doLayout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self.itemList:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        size += QSize(m.left()+m.right(), m.top()+m.bottom())
        return size

    def doLayout(self, rect, testOnly):
        x, y, lineHeight = rect.x(), rect.y(), 0
        for item in self.itemList:
            spaceX = self._spacing
            spaceY = self._spacing
            nextX = x + item.sizeHint().width() + spaceX
            if nextX - spaceX > rect.right() and lineHeight > 0:
                x = rect.x()
                y += lineHeight + spaceY
                nextX = x + item.sizeHint().width() + spaceX
                lineHeight = 0
            if not testOnly:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))
            x = nextX
            lineHeight = max(lineHeight, item.sizeHint().height())
        return y + lineHeight - rect.y()

    def moveItem(self, from_idx, to_idx):
        if 0 <= from_idx < len(self.itemList) and 0 <= to_idx <= len(self.itemList):
            item = self.itemList.pop(from_idx)
            self.itemList.insert(to_idx, item)
            self.invalidate()
            # Force immediate layout update
            if self.parentWidget():
                self.parentWidget().updateGeometry()

    # def doLayout(self, rect, testOnly):
    #     x,y,lineH = rect.x(), rect.y(), 0
    #     for item in self.itemList:
    #         w = item.sizeHint().width(); h=item.sizeHint().height()
    #         nx = x + w + self._spacing
    #         if nx - self._spacing > rect.right() and lineH>0:
    #             x=rect.x(); y+=lineH+self._spacing; nx=x+w+self._spacing; lineH=0
    #         target = QRect(QPoint(x,y), item.sizeHint())
    #         if not testOnly:
    #             anim = QPropertyAnimation(item.widget(), b"geometry")
    #             anim.setDuration(150)
    #             anim.setStartValue(item.widget().geometry())
    #             anim.setEndValue(target)
    #             anim.start()
    #         x=nx; lineH=max(lineH, h)
    #     return y+lineH-rect.y()