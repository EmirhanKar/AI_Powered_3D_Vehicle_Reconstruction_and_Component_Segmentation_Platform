class kitap:
    def init(self, kitap_ismi, sayfa_sayisi, kitap_turu, yazar):
        self.kitap_ismi = kitap_ismi
        self.sayfa_sayisi = sayfa_sayisi
        self.kitap_turu = kitap_turu
        self.yazar = yazar

    def bilgileri_goster(self):
        print("Kitap adı:", self.kitap_ismi)
        print("Yazar:", self.yazar)
        print("Sayfa sayısı:", self.sayfa_sayisi)
        print("Tür:", self.kitap_turu)

    def kitap_ekle():
        ismi = input("Kitap adı: ")
        yazar = input("Yazar: ")
        sayfa = input("Sayfa sayısı: ")
        turu = input("Tür: ")
        
        if turu == "Basılı Kitap":
            adet = int(input("Adet: "))
            yeni = basili_kitap(ismi, sayfa, turu, yazar, adet)
        else:
            alan = input("Hafıza alanı: ")
            yeni = e_kitap(ismi, sayfa, turu, yazar, alan)
            
        print("\nKitap başarıyla eklendi.")
        return yeni

class basili_kitap(kitap):
    def init(self, kitap_ismi, sayfa_sayisi, kitap_turu, yazar, adet):
        super().init(kitap_ismi, sayfa_sayisi, kitap_turu, yazar)
        self.adet = adet

    def odunc_al(self):
        if self.adet > 0:
            self.adet = self.adet - 1
            print("Kitap ödünç alındı. Kalan stok:", self.adet)
        else:
            print("Stok yetersiz!")

    def geri_teslim_et(self):
        self.adet = self.adet + 1
        print("Kitap geri teslim edildi. Yeni stok:", self.adet)

class e_kitap(kitap):
    def init(self, kitap_ismi, sayfa_sayisi, kitap_turu, yazar, hafiza_alani):
        super().init(kitap_ismi, sayfa_sayisi, kitap_turu, yazar)
        self.hafiza_alani = hafiza_alani

liste = []

while True:
    print("\n1- Kitap Ekle")
    print("2- Kitapları Listele")
    print("3- Kitap Ödünç Al")
    print("4- Kitap İade Et")
    print("5- Çıkış")
    
    secim = input("\nSeçim: ")

    if secim == "1":
        yeni = kitap.kitap_ekle()
        liste.append(yeni)

    elif secim == "2":
        if len(liste) == 0:
            print("Liste boş.")
        else:
            for k in liste:
                print("---")
                k.bilgileri_goster()
                if isinstance(k, basili_kitap):
                    print("Adet:", k.adet)
                if isinstance(k, e_kitap):
                    print("Hafıza alanı:", k.hafiza_alani)

    elif secim == "3":
        for i in range(len(liste)):
            print(i, "-", liste[i].kitap_ismi)
        no = int(input("No seçin: "))
        ktp = liste[no]
        if isinstance(ktp, basili_kitap):
            ktp.odunc_al()
        else:
            print("E-Kitap ödünç alınamaz.")

    elif secim == "4":
        for i in range(len(liste)):
            print(i, "-", liste[i].kitap_ismi)
        no = int(input("No seçin: "))
        ktp = liste[no]
        if isinstance(ktp, basili_kitap):
            ktp.geri_teslim_et()
        else:
            print("E-kitaplar iade edilemez.")

    elif secim == "5":
        print("Güle güle iyi çalışmalar dileriz.")
        break