Bu proje, araç sahiplerinin fiziksel modifikasyon yapmadan önce araçları üzerinde gerçekleştirecekleri görsel değişiklikleri yüksek doğrulukla simüle edebilecekleri bir dijital platform geliştirmeyi amaçlamaktadır.
Sistem; çoklu bakış açılı görüntülerden derinlik haritası üretmek için DepthAnything V3 modelini kullanmakta ve bu verileri Open3D ile 3B nokta bulutuna dönüştürmektedir. 
Araç parçalarının tespiti için segmentasyon modelleri uygulanmış ve modüler bir analiz hattı oluşturulmuştur. 
Backend tarafında FastAPI tabanlı asenkron bir mimari geliştirilmiş, veri yönetimi PostgreSQL ve SQLAlchemy ile sağlanmıştır. 
Güvenlik amacıyla JWT tabanlı kimlik doğrulama kullanılmıştır. 
Mobil arayüz Flutter ile geliştirilerek kullanıcıların kolay ve etkileşimli bir deneyim elde etmesi sağlanmıştır. 
Proje, yapay zekâ ve görüntü işleme teknolojilerini birleştirerek otomotiv modifikasyon süreçlerini dijital ortama taşıyan yenilikçi bir çözüm sunmaktadır.
